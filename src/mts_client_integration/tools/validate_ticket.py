"""MCP tool for ticket validation."""

from __future__ import annotations

from typing import cast

from fastmcp import FastMCP

from mts_client_integration.models.mcp_outputs import ValidationOutput
from mts_client_integration.services.validation import validate_request_payload


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def validate_ticket_request(
        payload: dict[str, object] | str,
        operation: str | None = None,
        session_state: list[dict[str, object]] | str | None = None,
        reference_time_utc_ms: int | None = None,
        serialized_bytes: int | None = None,
    ) -> ValidationOutput:
        """Validate a Ticket 3.0 request payload before sending it to MTS.

        For outbound **request** envelopes only — not for MTS reply/response
        validation. Do not pass inbound ``*-reply`` messages as ``payload``;
        use ``mts://schemas/ticket3/response`` to inspect response shape.

        Use when building or reviewing outbound Ticket 3.0 JSON to catch,
        locally, the issues that otherwise surface as MTS rejections
        (``-1xx``/``-2xx``/``-3xx``). Runs four layers in one pass:

        1. **Schema** — JSON Schema validation (shape / required fields).
        2. **Envelope** — typed parse + ``operation`` ↔ ``content.type`` check.
        3. **Business rules** — selection cap (100), positive stake, min odds
           (1.01), currency format, system ``size`` validity + predefined
           permutations (Trixie/Yankee/…), ways same-event, non-SR-in-system and
           banker-on-non-SR, Custom Bet anti-multiplication + caps, cumulative
           partial cash-out percentage,
           channel/language expectations, frame-size (32 KB x 4), and more.
        4. **ACK / nACK state machine** — the cancellation ACK matrix and the
           ticket-placement acknowledgement flow (``ticket-reply`` ->
           ``ticket-ack``/nACK), derived from ``session_state``.

        ## How to construct the input

        Direction is always from the integrator's (client's) point of view:
        *outbound* = client → MTS (requests and ACKs); *inbound* = MTS → client
        (responses, whose ``content.type`` ends in ``-reply``).

        **payload** — the single outbound request envelope you are about to
        send, verbatim as it goes over the WebSocket::

            {"operatorId": "...", "content": {...}, "correlationId": "...",
             "timestampUtc": 1745311871018, "operation": "...", "version": "3.0"}

        Pass exactly one message here: the one being validated. Do NOT include
        earlier messages — those belong in ``session_state``.

        **operation** — optional; when given it must match ``payload.operation``.

        **session_state** — the messages already exchanged for this ticket in
        the current session, in chronological order, EXCLUDING ``payload``. It
        supplies the history needed for stateful business rules (cumulative
        cash-out percentage, monotonic factor, placement currency) and the ACK /
        nACK flow. Omit it for a first, stateless placement. Two forms:

        - a structured list of ``{"direction": "outbound" | "inbound",
          "message": {<envelope>}}`` entries (``direction`` is optional and
          inferred: an envelope with ``operatorId`` or a non-``*-reply``
          ``content.type`` is outbound, a ``*-reply`` is inbound), or
        - a raw pasted log dump (string) with ``->``/``<-`` (or
          ``request:``/``response:``) markers.

        Messages are paired by ``correlationId``; ACKs match by
        ``cancellationId`` / ``cashoutId`` (falling back to ``ticketId``).

        Example — a follow-up partial cash-out. Send the new ``ticket-cashout``
        as ``payload`` and put the placement + earlier cash-out(s) in
        ``session_state``::

            payload = {new ticket-cashout envelope}
            session_state = [
              {"direction": "outbound", "message": {ticket-placement envelope}},
              {"direction": "outbound", "message": {prior ticket-cashout envelope}},
            ]

        See the ``mts://schemas/session-state`` MCP resource for the full shape.

        **reference_time_utc_ms** — clock for ``timestampUtc`` checks; defaults
        to now.

        **serialized_bytes** — byte length of the serialized message for the
        frame-size rule; defaults to the encoded ``payload`` size.

        Returns ``schema_ok`` / ``envelope_ok`` / ``business_rules_ok`` /
        ``ack_state_machine_ok`` booleans plus structured issue lists. Each
        business rule / ACK issue carries a ``severity`` (``error`` / ``warning``
        / ``info``); only ``error`` flips the matching ``*_ok`` flag. Messages in
        ``session_state`` that cannot be parsed or paired appear in
        ``session_state_errors``.
        """
        result = validate_request_payload(
            payload,
            operation=operation,
            session_state=session_state,
            reference_time_utc_ms=reference_time_utc_ms,
            serialized_bytes=serialized_bytes,
        )
        return cast(ValidationOutput, result.to_response_dict())
