"""Background WebSocket mock server for local MTS integration testing."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from mts_client_integration.models.business_rules import MAX_MESSAGE_BYTES
from mts_client_integration.services.simulator.catalog import (
    DEFAULT_WS_PORT,
    INJECT_EVENTS,
    RATE_LIMIT_RPS,
    expand_scenarios,
    valid_scenario_ids,
)
from mts_client_integration.services.simulator.handlers import MessageHandler, RateLimiter
from mts_client_integration.services.simulator.protocol import FrameAssembler, FrameProtocolError
from mts_client_integration.services.simulator.session import (
    ConnectionState,
    MockSession,
    ReconnectRecord,
)

logger = logging.getLogger(__name__)

AuthMode = Literal["lenient", "strict"]
RateLimitProfile = Literal["integration", "production"]

_MANAGER_CALL_TIMEOUT_SECONDS = 10
_THREAD_JOIN_TIMEOUT_SECONDS = 5
_HEARTBEAT_INTERVAL_SECONDS = 20
_OAUTH_READ_TIMEOUT_SECONDS = 5
_OAUTH_MAX_HEADER_LINES = 100


class MockServerError(RuntimeError):
    """Raised when a mock server operation cannot be completed; message is actionable."""


@dataclass
class MockConfig:
    scenarios: list[str] = field(default_factory=lambda: ["realistic_mix"])
    rate_limit_profile: RateLimitProfile = "integration"
    ws_port: int | None = None
    oauth_port: int | None = None
    connection_ttl_seconds: int = 7200
    auth_mode: AuthMode = "lenient"
    scenario_params: dict[str, dict[str, Any]] | None = None


@dataclass
class MockStartResult:
    session_id: str
    ws_url: str
    oauth_url: str
    ws_port: int
    oauth_port: int
    scenarios_active: list[str]
    rate_limit_rps: int | None
    connection_ttl_seconds: int
    fixture_driven: bool = True
    agent_guidance: str = (
        "Point your MTS client at ws_url. Use inject() for connection_blocked. "
        "Call stop_mock() when done and pass wire_log to validate_ticket_request."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "ws_url": self.ws_url,
            "oauth_url": self.oauth_url,
            "ws_port": self.ws_port,
            "oauth_port": self.oauth_port,
            "scenarios_active": self.scenarios_active,
            "rate_limit_rps": self.rate_limit_rps,
            "connection_ttl_seconds": self.connection_ttl_seconds,
            "fixture_driven": self.fixture_driven,
            "agent_guidance": self.agent_guidance,
        }


async def _discard_http_headers(reader: asyncio.StreamReader) -> None:
    """Consume request headers up to the blank line; reject unbounded header sections."""
    for _ in range(_OAUTH_MAX_HEADER_LINES):
        line = await reader.readline()
        if line in (b"", b"\r\n", b"\n"):
            return
    msg = f"more than {_OAUTH_MAX_HEADER_LINES} header lines"
    raise ValueError(msg)


class MockServerRuntime:
    """Async runtime owned by a background event-loop thread."""

    def __init__(self, config: MockConfig) -> None:
        expanded = expand_scenarios(config.scenarios)
        self.config = config
        self.session = MockSession(
            session_id=f"mock-{uuid.uuid4().hex[:12]}",
            started_at=time.time(),
            scenarios_active=expanded.active,
        )
        self.connection_blocked = False
        self._connections: set[ServerConnection] = set()
        self._ttl_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        # Strong references: the event loop only keeps weak refs to running tasks.
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._oauth_server: asyncio.Server | None = None
        self._ws_server: Server | None = None
        self._ws_port = 0
        self._oauth_port = 0
        self._first_connect_at: float | None = None

        rate_params = (config.scenario_params or {}).get("rate_limit", {})
        burst = rate_params.get("burst")
        burst_int = int(burst) if isinstance(burst, int | float) else None
        self._rate_limiter: RateLimiter | None = None
        if "rate_limit" in expanded.active:
            rps = RATE_LIMIT_RPS[config.rate_limit_profile]
            self._rate_limiter = RateLimiter(float(rps), burst=burst_int)

    @property
    def rate_limit_rps(self) -> int | None:
        if "rate_limit" not in self.session.scenarios_active:
            return None
        return RATE_LIMIT_RPS[self.config.rate_limit_profile]

    async def start_servers(self) -> MockStartResult:
        ws_port = self.config.ws_port if self.config.ws_port is not None else DEFAULT_WS_PORT
        oauth_requested = self.config.oauth_port
        if oauth_requested is None:
            oauth_requested = (ws_port + 1) if ws_port != 0 else 0

        self._ws_server = await serve(
            self._ws_handler,
            "127.0.0.1",
            ws_port,
            max_size=MAX_MESSAGE_BYTES,
        )
        self._ws_port = int(self._ws_server.sockets[0].getsockname()[1])

        oauth_bind = oauth_requested if oauth_requested != 0 else 0
        self._oauth_server = await asyncio.start_server(
            self._oauth_handler,
            "127.0.0.1",
            oauth_bind,
        )
        self._oauth_port = int(self._oauth_server.sockets[0].getsockname()[1])

        if "spam_detector" in self.session.scenarios_active:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        return MockStartResult(
            session_id=self.session.session_id,
            ws_url=f"ws://127.0.0.1:{self._ws_port}",
            oauth_url=f"http://127.0.0.1:{self._oauth_port}/token",
            ws_port=self._ws_port,
            oauth_port=self._oauth_port,
            scenarios_active=sorted(self.session.scenarios_active),
            rate_limit_rps=self.rate_limit_rps,
            connection_ttl_seconds=self.config.connection_ttl_seconds,
        )

    async def stop_servers(self) -> None:
        for task in (self._ttl_task, self._heartbeat_task, *self._background_tasks):
            if task is not None:
                task.cancel()
        await self._drop_all_connections(1000, "mock server stopping")
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        if self._oauth_server is not None:
            self._oauth_server.close()
            await self._oauth_server.wait_closed()

    async def inject(
        self,
        event: str,
        *,
        duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        if event not in INJECT_EVENTS:
            raise ValueError(f"Unknown inject event: {event}")

        if event == "connection_blocked":
            self.connection_blocked = True
            await self._drop_all_connections(1001, "connection blocked by inject")
            if duration_seconds is not None and duration_seconds > 0:
                task = asyncio.create_task(self._auto_unblock(duration_seconds))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            return {
                "ok": True,
                "event": event,
                "params_applied": {"duration_seconds": duration_seconds},
            }

        if event == "connection_unblocked":
            self.connection_blocked = False
            return {"ok": True, "event": event, "params_applied": {}}

        if event == "force_disconnect":
            await self._drop_all_connections(1001, "force disconnect by inject")
            return {"ok": True, "event": event, "params_applied": {}}

        if event == "fast_forward_timer":
            await self._fire_ttl_close()
            return {"ok": True, "event": event, "params_applied": {}}

        return {"ok": False, "event": event, "error": "unhandled event"}

    def status(self) -> dict[str, Any]:
        return {
            "running": True,
            "session_id": self.session.session_id,
            "blocked": self.connection_blocked,
            "connections": len(self._connections),
            "messages_in": self.session.metrics.messages_in,
            "messages_out": self.session.metrics.messages_out,
            "rate_limit_rejections": self.session.metrics.rate_limit_rejections,
            "reconnect_attempts": [
                {"timestamp_utc_ms": r.timestamp_utc_ms, "remote_address": r.remote_address}
                for r in self.session.metrics.reconnect_attempts
            ],
            "scenarios_active": sorted(self.session.scenarios_active),
            "fixture_driven": True,
        }

    def stop_summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session.session_id,
            "wire_log": self.session.wire_log_as_session_state(),
            "metrics": self.session.metrics.to_dict(),
            "duration_seconds": round(self.session.duration_seconds(), 3),
            "fixture_driven": True,
        }

    async def _auto_unblock(self, seconds: int) -> None:
        await asyncio.sleep(seconds)
        self.connection_blocked = False

    async def _ws_handler(self, websocket: ServerConnection) -> None:
        if self.connection_blocked:
            await websocket.close(1001, "connection blocked")
            return

        remote = str(websocket.remote_address or "unknown")
        if "spam_detector" in self.session.scenarios_active:
            self.session.metrics.reconnect_attempts.append(
                ReconnectRecord(timestamp_utc_ms=int(time.time() * 1000), remote_address=remote)
            )

        if self.config.auth_mode == "strict":
            auth = websocket.request.headers.get("Authorization") if websocket.request else None
            if not auth:
                await websocket.close(1008, "authorization required")
                return

        self._connections.add(websocket)
        self.session.metrics.connections = len(self._connections)

        if "token_2h_handover" in self.session.scenarios_active and self._ttl_task is None:
            self._first_connect_at = time.time()
            self._ttl_task = asyncio.create_task(self._ttl_loop())

        assembler = FrameAssembler() if "frame_split" in self.session.scenarios_active else None
        conn_state = ConnectionState()
        handler = MessageHandler(
            self.session,
            scenario_params=self.config.scenario_params,
            rate_limiter=self._rate_limiter,
        )
        use_frames = assembler is not None

        try:
            async for message in websocket:
                try:
                    if use_frames and assembler is not None:
                        envelope = assembler.feed(message)
                        if envelope is None:
                            continue
                    else:
                        text = message.decode("utf-8") if isinstance(message, bytes) else message
                        parsed = json.loads(text)
                        if not isinstance(parsed, dict):
                            continue
                        envelope = parsed

                    self.session.log_outbound(envelope)
                    reply = handler.handle(envelope, conn_state)
                    if reply is not None:
                        self.session.log_inbound(reply)
                        await websocket.send(json.dumps(reply))
                except FrameProtocolError as exc:
                    await websocket.close(exc.code, exc.reason)
                    break
                except json.JSONDecodeError, UnicodeDecodeError:
                    await websocket.close(1007, "invalid JSON")
                    break
        except ConnectionClosed:
            pass
        finally:
            self._connections.discard(websocket)
            self.session.metrics.connections = len(self._connections)

    async def _oauth_handler(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            try:
                async with asyncio.timeout(_OAUTH_READ_TIMEOUT_SECONDS):
                    await _discard_http_headers(reader)
            except (TimeoutError, ValueError) as exc:
                logger.warning("Dropping malformed or stalled OAuth request: %r", exc)
                return
            body = json.dumps(
                {
                    "access_token": "mock-mts-token",
                    "token_type": "Bearer",
                    "expires_in": self.config.connection_ttl_seconds,
                }
            ).encode()
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            writer.write(response)
            await writer.drain()
        except ConnectionError as exc:
            logger.warning("OAuth client disconnected before the response was sent: %r", exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError as exc:
                logger.debug("OAuth connection reset while closing: %r", exc)

    async def _ttl_loop(self) -> None:
        await asyncio.sleep(self.config.connection_ttl_seconds)
        await self._fire_ttl_close()

    async def _fire_ttl_close(self) -> None:
        await self._drop_all_connections(1000, "connection TTL reached (token_2h_handover)")

    async def _drop_all_connections(self, code: int, reason: str) -> None:
        for ws in list(self._connections):
            try:
                await ws.close(code, reason)
            except (ConnectionClosed, OSError) as exc:
                logger.debug("Connection already gone while closing (%s): %r", reason, exc)
        self._connections.clear()
        self.session.metrics.connections = 0

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)
            for ws in list(self._connections):
                try:
                    await ws.ping()
                except (ConnectionClosed, OSError) as exc:
                    logger.debug("Heartbeat ping failed; dropping connection: %r", exc)
                    self._connections.discard(ws)


class MockServerManager:
    """Thread-safe facade for sync MCP tool handlers.

    Owns at most one background event-loop thread running a ``MockServerRuntime``.
    All failures raise ``MockServerError`` with an actionable message.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runtime: MockServerRuntime | None = None
        self._start_result: MockStartResult | None = None
        self._start_error: str | None = None
        self._ready = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, config: MockConfig) -> dict[str, Any]:
        expanded = expand_scenarios(config.scenarios)
        if expanded.invalid:
            msg = (
                f"Unknown scenario(s): {', '.join(expanded.invalid)}. "
                f"Valid IDs: {', '.join(valid_scenario_ids())}"
            )
            raise MockServerError(msg)
        with self._lock:
            if self.is_running:
                msg = "Mock server already running. Call stop_mock() first."
                raise MockServerError(msg)
            self._ready.clear()
            self._start_error = None
            self._thread = threading.Thread(target=self._run_thread, args=(config,), daemon=True)
            self._thread.start()
        ready = self._ready.wait(timeout=_MANAGER_CALL_TIMEOUT_SECONDS)
        with self._lock:
            start_error = self._start_error
            start_result = self._start_result
        if start_error is not None:
            self._reset_after_failed_start(stop_loop=False)
            msg = (
                f"Mock server failed to start: {start_error}. "
                "Pass ws_port=0 and oauth_port=0 to bind free ports."
            )
            raise MockServerError(msg)
        if not ready or start_result is None:
            self._reset_after_failed_start(stop_loop=True)
            msg = f"Mock server failed to start within {_MANAGER_CALL_TIMEOUT_SECONDS} seconds"
            raise MockServerError(msg)
        return {"ok": True, **start_result.to_dict()}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self.is_running or self._loop is None or self._runtime is None:
                msg = "No mock server is running."
                raise MockServerError(msg)
            loop = self._loop
            runtime = self._runtime
        shutdown_error: str | None = None
        future = asyncio.run_coroutine_threadsafe(runtime.stop_servers(), loop)
        try:
            future.result(timeout=_MANAGER_CALL_TIMEOUT_SECONDS)
        except TimeoutError:
            future.cancel()
            shutdown_error = f"did not shut down within {_MANAGER_CALL_TIMEOUT_SECONDS} seconds"
        summary = runtime.stop_summary()
        self._terminate_loop(loop)
        if shutdown_error is not None:
            logger.warning("Mock server %s; loop was stopped forcibly", shutdown_error)
            msg = f"Mock server {shutdown_error}; it was stopped forcibly and its state reset."
            raise MockServerError(msg)
        return {"ok": True, **summary}

    def inject(self, event: str, *, duration_seconds: int | None = None) -> dict[str, Any]:
        runtime, loop = self._require_runtime()
        future = asyncio.run_coroutine_threadsafe(
            runtime.inject(event, duration_seconds=duration_seconds),
            loop,
        )
        try:
            return future.result(timeout=_MANAGER_CALL_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            future.cancel()
            msg = f"Inject event {event!r} did not complete within {_MANAGER_CALL_TIMEOUT_SECONDS}s"
            raise MockServerError(msg) from exc

    def status(self) -> dict[str, Any]:
        with self._lock:
            runtime = self._runtime
            start_result = self._start_result
            running = self.is_running
        if not running or runtime is None:
            return {"running": False, "fixture_driven": True}
        result = runtime.status()
        if start_result is not None:
            result["ws_url"] = start_result.ws_url
            result["oauth_url"] = start_result.oauth_url
        return result

    def active_ws_url(self) -> str | None:
        with self._lock:
            if not self.is_running or self._start_result is None:
                return None
            return self._start_result.ws_url

    def active_oauth_url(self) -> str | None:
        with self._lock:
            if not self.is_running or self._start_result is None:
                return None
            return self._start_result.oauth_url

    def _require_runtime(self) -> tuple[MockServerRuntime, asyncio.AbstractEventLoop]:
        with self._lock:
            if not self.is_running or self._runtime is None or self._loop is None:
                msg = "No mock server is running. Call start_mock() first."
                raise MockServerError(msg)
            return self._runtime, self._loop

    def _terminate_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Stop the background loop, join its thread, and reset all manager state."""
        if not loop.is_closed():
            loop.call_soon_threadsafe(loop.stop)
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)
        with self._lock:
            self._thread = None
            self._loop = None
            self._runtime = None
            self._start_result = None

    def _reset_after_failed_start(self, *, stop_loop: bool) -> None:
        with self._lock:
            loop = self._loop
        if loop is not None and stop_loop:
            self._terminate_loop(loop)
            return
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)
        with self._lock:
            self._thread = None
            self._loop = None
            self._runtime = None
            self._start_result = None

    def _run_thread(self, config: MockConfig) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
        runtime: MockServerRuntime | None = None
        try:
            runtime = MockServerRuntime(config)
            with self._lock:
                self._runtime = runtime
            result = loop.run_until_complete(runtime.start_servers())
            with self._lock:
                self._start_result = result
            self._ready.set()
            loop.run_forever()
        except Exception as exc:  # reported to the caller via _start_error
            logger.exception("Mock server thread failed")
            if runtime is not None:
                # A partially started runtime may still hold a bound WS socket.
                try:
                    loop.run_until_complete(runtime.stop_servers())
                except Exception:
                    logger.exception("Failed to release sockets of partially started mock server")
            with self._lock:
                self._start_error = str(exc)
            self._ready.set()
        finally:
            loop.close()
