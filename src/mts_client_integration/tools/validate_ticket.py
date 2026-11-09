"""MCP-facing ticket validation tool."""

from __future__ import annotations

from typing import Any

from mts_client_integration.models.validation import ValidationResult
from mts_client_integration.services.validation import validate_request_payload


def validate_ticket_request(
    payload: dict[str, Any] | str,
    *,
    operation: str | None = None,
    session_state: object | None = None,
    reference_time_utc_ms: int | None = None,
    serialized_bytes: int | None = None,
) -> ValidationResult:
    """Validate an outbound Ticket 3.0 request across all four validation layers.

    Thin wrapper over ``validate_request_payload``; the MCP tool docstring in
    ``mcp_server`` is the agent-facing contract for the inputs.
    """
    return validate_request_payload(
        payload,
        operation=operation,
        session_state=session_state,
        reference_time_utc_ms=reference_time_utc_ms,
        serialized_bytes=serialized_bytes,
    )
