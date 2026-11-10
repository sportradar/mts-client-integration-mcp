"""Client-side operations against a running local mock server."""

from __future__ import annotations

from typing import Any

from mts_client_integration.services.simulator.server import MockServerError, MockServerManager
from mts_client_integration.services.simulator.wire_client import (
    fetch_mock_oauth_token,
    send_messages,
)


def resolve_outbound_messages(
    payload: dict[str, Any] | None,
    messages: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Resolve a single payload or message list into envelopes to send."""
    if messages is not None:
        if not messages:
            msg = "messages must not be empty; pass at least one envelope."
            raise ValueError(msg)
        return messages
    if payload is not None:
        return [payload]
    msg = "Provide payload or a non-empty messages list."
    raise ValueError(msg)


def send_to_running_mock(
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
    outbound = resolve_outbound_messages(payload, messages)
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
