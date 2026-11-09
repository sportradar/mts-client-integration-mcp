"""WebSocket client for sending Ticket 3.0 traffic to the local mock server."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, cast
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, WebSocketException


@dataclass(frozen=True)
class WireExchange:
    """One outbound envelope and the mock's inbound reply, if any."""

    sent: dict[str, Any]
    reply: dict[str, Any] | None
    reply_received: bool
    error: str | None = None


@dataclass(frozen=True)
class WireSendResult:
    """Outcome of a send_to_mock call."""

    ok: bool
    ws_url: str
    exchanges: list[WireExchange]
    connection_close_code: int | None = None
    connection_close_reason: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "ws_url": self.ws_url,
            "exchanges": [
                {
                    "sent": ex.sent,
                    "reply": ex.reply,
                    "reply_received": ex.reply_received,
                    **({"error": ex.error} if ex.error else {}),
                }
                for ex in self.exchanges
            ],
            **(
                {"connection_close_code": self.connection_close_code}
                if self.connection_close_code is not None
                else {}
            ),
            **(
                {"connection_close_reason": self.connection_close_reason}
                if self.connection_close_reason
                else {}
            ),
            **({"error": self.error} if self.error else {}),
        }


def fetch_mock_oauth_token(oauth_url: str, *, timeout_seconds: float = 5.0) -> str:
    """Fetch a Bearer token from the mock's stub OAuth endpoint."""
    if urlsplit(oauth_url).scheme not in ("http", "https"):
        msg = f"OAuth URL must use http or https: {oauth_url}"
        raise ValueError(msg)
    try:
        with urlopen(oauth_url, timeout=timeout_seconds) as response:  # noqa: S310
            body = json.loads(response.read().decode())
    except URLError as exc:
        raise RuntimeError(f"Failed to fetch OAuth token from {oauth_url}: {exc}") from exc

    if not isinstance(body, dict):
        raise RuntimeError(f"Unexpected OAuth response from {oauth_url}")
    token = body.get("access_token")
    if not isinstance(token, str):
        raise RuntimeError(f"OAuth response missing access_token: {oauth_url}")
    token_type = body.get("token_type")
    if isinstance(token_type, str) and token_type.lower() == "bearer":
        return f"Bearer {token}"
    return token if token.startswith("Bearer ") else f"Bearer {token}"


def _parse_json_message(raw: str | bytes) -> dict[str, Any]:
    text = raw.decode() if isinstance(raw, bytes) else raw
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        msg = "Mock reply was not a JSON object"
        raise TypeError(msg)
    return cast(dict[str, Any], parsed)


async def _exchange(
    ws: ClientConnection,
    envelope: dict[str, Any],
    *,
    timeout_seconds: float,
) -> WireExchange:
    """Send one envelope and wait for the reply; reply problems become exchange errors.

    ``ConnectionClosed`` is deliberately not handled here: the caller owns
    connection-level bookkeeping (close code, loop termination).
    """
    await ws.send(json.dumps(envelope))
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
    except TimeoutError:
        return WireExchange(
            sent=envelope,
            reply=None,
            reply_received=False,
            error=f"No reply within {timeout_seconds}s",
        )
    try:
        reply = _parse_json_message(raw)
    except (ValueError, TypeError) as exc:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        return WireExchange(
            sent=envelope,
            reply=None,
            reply_received=True,
            error=f"Mock reply is not a valid JSON object: {exc}",
        )
    return WireExchange(sent=envelope, reply=reply, reply_received=True)


def _closed_exchange(envelope: dict[str, Any], exc: Exception) -> WireExchange:
    return WireExchange(sent=envelope, reply=None, reply_received=False, error=str(exc))


async def send_messages_async(
    ws_url: str,
    messages: list[dict[str, Any]],
    *,
    reuse_connection: bool = True,
    timeout_seconds: float = 10.0,
    authorization: str | None = None,
    open_timeout_seconds: float = 5.0,
) -> WireSendResult:
    """Send one or more Ticket 3.0 envelopes to the mock WebSocket server."""
    if not messages:
        return WireSendResult(ok=False, ws_url=ws_url, exchanges=[], error="No messages to send")

    headers = {"Authorization": authorization} if authorization else None
    exchanges: list[WireExchange] = []
    close_code: int | None = None
    close_reason: str | None = None

    def open_connection() -> connect:
        return connect(ws_url, additional_headers=headers, open_timeout=open_timeout_seconds)

    try:
        if reuse_connection:
            async with open_connection() as ws:
                for envelope in messages:
                    try:
                        exchanges.append(
                            await _exchange(ws, envelope, timeout_seconds=timeout_seconds)
                        )
                    except ConnectionClosed as exc:
                        exchanges.append(_closed_exchange(envelope, exc))
                        break
                if ws.close_code is not None:
                    close_code, close_reason = ws.close_code, ws.close_reason
        else:
            for envelope in messages:
                try:
                    async with open_connection() as ws:
                        exchanges.append(
                            await _exchange(ws, envelope, timeout_seconds=timeout_seconds)
                        )
                        if ws.close_code is not None:
                            close_code, close_reason = ws.close_code, ws.close_reason
                except (WebSocketException, OSError) as exc:
                    exchanges.append(_closed_exchange(envelope, exc))
                    close_code, close_reason = _close_info(exc, close_code, close_reason)
    except (WebSocketException, OSError, TimeoutError) as exc:
        code, reason = _close_info(exc, None, None)
        return WireSendResult(
            ok=False,
            ws_url=ws_url,
            exchanges=exchanges,
            connection_close_code=code,
            connection_close_reason=reason,
            error=str(exc),
        )

    ok = bool(exchanges) and all(ex.error is None for ex in exchanges)
    return WireSendResult(
        ok=ok,
        ws_url=ws_url,
        exchanges=exchanges,
        connection_close_code=close_code,
        connection_close_reason=close_reason,
    )


def _close_info(
    exc: Exception,
    previous_code: int | None,
    previous_reason: str | None,
) -> tuple[int | None, str | None]:
    """Extract close code/reason from a connection error, keeping prior values otherwise."""
    if isinstance(exc, ConnectionClosed) and exc.rcvd is not None:
        return exc.rcvd.code, exc.rcvd.reason or None
    return previous_code, previous_reason


def send_messages(
    ws_url: str,
    messages: list[dict[str, Any]],
    *,
    reuse_connection: bool = True,
    timeout_seconds: float = 10.0,
    authorization: str | None = None,
    open_timeout_seconds: float = 5.0,
) -> WireSendResult:
    """Sync wrapper around :func:`send_messages_async` for MCP tool handlers."""
    return asyncio.run(
        send_messages_async(
            ws_url,
            messages,
            reuse_connection=reuse_connection,
            timeout_seconds=timeout_seconds,
            authorization=authorization,
            open_timeout_seconds=open_timeout_seconds,
        ),
    )
