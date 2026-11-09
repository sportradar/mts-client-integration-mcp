"""Service-facing helpers for the MCP simulator tools.

Every function takes the ``MockServerManager`` owned by the server lifespan and raises
``MockServerError`` (or ``ValueError`` for invalid input) on failure; the MCP layer
converts those into ``ToolError``.
"""

from __future__ import annotations

from typing import Any, Literal

from mts_client_integration.services.simulator.catalog import get_catalog_documentation
from mts_client_integration.services.simulator.server import (
    MockConfig,
    MockServerError,
    MockServerManager,
)
from mts_client_integration.services.simulator.wire_client import (
    fetch_mock_oauth_token,
    send_messages,
)

RateLimitProfile = Literal["integration", "production"]
AuthMode = Literal["lenient", "strict"]
InjectEvent = Literal[
    "connection_blocked",
    "connection_unblocked",
    "force_disconnect",
    "fast_forward_timer",
]


def list_mock_scenarios() -> dict[str, Any]:
    """Return the closed catalog of scenario IDs, bundles, and inject events."""
    return get_catalog_documentation()


def start_mock(
    manager: MockServerManager,
    scenarios: list[str] | None = None,
    rate_limit_profile: RateLimitProfile = "integration",
    ws_port: int | None = None,
    oauth_port: int | None = None,
    connection_ttl_seconds: int = 7200,
    auth_mode: AuthMode = "lenient",
    scenario_params: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Start the fixture-driven local MTS WebSocket mock server."""
    config = MockConfig(
        scenarios=list(scenarios) if scenarios is not None else ["realistic_mix"],
        rate_limit_profile=rate_limit_profile,
        ws_port=ws_port,
        oauth_port=oauth_port,
        connection_ttl_seconds=connection_ttl_seconds,
        auth_mode=auth_mode,
        scenario_params=scenario_params,
    )
    return manager.start(config)


def stop_mock(manager: MockServerManager) -> dict[str, Any]:
    """Stop the running mock server and return wire log + metrics."""
    return manager.stop()


def inject_mock(
    manager: MockServerManager,
    event: InjectEvent,
    duration_seconds: int | None = None,
) -> dict[str, Any]:
    """Inject a mid-session connectivity or timer event into the running mock."""
    return manager.inject(event, duration_seconds=duration_seconds)


def mock_status(manager: MockServerManager) -> dict[str, Any]:
    """Poll mock server status without stopping it."""
    return manager.status()


def send_to_mock(
    manager: MockServerManager,
    payload: dict[str, Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
    *,
    reuse_connection: bool = True,
    timeout_seconds: float = 10.0,
    authorization: str | None = None,
    fetch_oauth_token: bool = False,
) -> dict[str, Any]:
    """Send Ticket 3.0 envelope(s) to the running local mock WebSocket server."""
    outbound = _resolve_outbound_messages(payload, messages)
    ws_url = manager.active_ws_url()
    if ws_url is None:
        msg = "No mock server is running. Call start_mock() first."
        raise MockServerError(msg)

    auth_header = authorization
    if fetch_oauth_token and not auth_header:
        oauth_url = manager.active_oauth_url()
        if oauth_url is None:
            msg = "Mock OAuth URL unavailable; pass authorization."
            raise MockServerError(msg)
        try:
            auth_header = fetch_mock_oauth_token(oauth_url)
        except RuntimeError as exc:
            raise MockServerError(str(exc)) from exc

    result = send_messages(
        ws_url,
        outbound,
        reuse_connection=reuse_connection,
        timeout_seconds=timeout_seconds,
        authorization=auth_header,
    )
    return result.to_dict()


def _resolve_outbound_messages(
    payload: dict[str, Any] | None,
    messages: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if messages is not None:
        if not messages:
            msg = "messages must not be empty; pass at least one envelope."
            raise ValueError(msg)
        return messages
    if payload is not None:
        return [payload]
    msg = "Provide payload or a non-empty messages list."
    raise ValueError(msg)
