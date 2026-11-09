"""Parse the session state: a history of raw Ticket 3.0 wire envelopes.

Accepts either a structured list (``{direction, message}`` entries or bare
envelopes) or a raw pasted log dump (string). Direction is inferred when not
given: outbound messages carry ``operatorId``; inbound responses have a
``content.type`` ending in ``-reply``. Messages that cannot be parsed surface
as ``SessionStateError`` rather than being silently dropped.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Literal

from mts_client_integration.models.business_rules import (
    PriorState,
    SessionStateEntry,
    SessionStateError,
    SessionStateParseResult,
)
from mts_client_integration.services.ticket_tree import (
    as_dict,
    as_list,
    as_str,
    extract_cancel,
    extract_cashout,
    extract_ticket,
    to_decimal,
)

Direction = Literal["outbound", "inbound"]

_OUTBOUND_MARKERS = ("->", "-->", "request:")
_INBOUND_MARKERS = ("<-", "<--", "response:")


def parse_session_state(session_state: object | None) -> SessionStateParseResult:
    """Parse a session_state input into typed entries plus per-message errors."""
    if session_state is None:
        return SessionStateParseResult()
    if isinstance(session_state, str):
        raw_entries = _extract_from_log(session_state)
    elif isinstance(session_state, list):
        raw_entries = _normalize_list(session_state)
    else:
        return SessionStateParseResult(
            errors=(SessionStateError("session_state must be a list or a log string."),)
        )

    entries: list[SessionStateEntry] = []
    errors: list[SessionStateError] = []
    for index, (direction, message, error) in enumerate(raw_entries):
        if error is not None:
            errors.append(SessionStateError(error, index=index))
            continue
        if message is None:
            continue
        resolved = direction or _infer_direction(message)
        entries.append(
            SessionStateEntry(
                direction=resolved,
                message=message,
                index=index,
                operation=as_str(message.get("operation")),
                correlation_id=as_str(message.get("correlationId")),
            )
        )
    errors.extend(_pairing_errors(entries))
    return SessionStateParseResult(entries=tuple(entries), errors=tuple(errors))


def _normalize_list(
    items: list[Any],
) -> list[tuple[Direction | None, dict[str, Any] | None, str | None]]:
    result: list[tuple[Direction | None, dict[str, Any] | None, str | None]] = []
    for item in items:
        item_dict = as_dict(item)
        if item_dict is None:
            result.append((None, None, "session_state entry is not an object."))
            continue
        if "message" in item_dict:
            message = as_dict(item_dict.get("message"))
            direction = _coerce_direction(item_dict.get("direction"))
            if message is None:
                result.append((None, None, "session_state entry 'message' is not an object."))
            else:
                result.append((direction, message, None))
        else:
            result.append((None, item_dict, None))
    return result


def _extract_from_log(
    text: str,
) -> list[tuple[Direction | None, dict[str, Any] | None, str | None]]:
    decoder = json.JSONDecoder()
    result: list[tuple[Direction | None, dict[str, Any] | None, str | None]] = []
    position = 0
    length = len(text)
    while position < length:
        brace = text.find("{", position)
        if brace == -1:
            break
        try:
            obj, end = decoder.raw_decode(text, brace)
        except json.JSONDecodeError:
            position = brace + 1
            continue
        if isinstance(obj, dict):
            direction = _direction_from_prefix(text, brace)
            result.append((direction, obj, None))
        position = end
    return result


def _direction_from_prefix(text: str, brace: int) -> Direction | None:
    line_start = text.rfind("\n", 0, brace) + 1
    prefix = text[line_start:brace].lower()
    if any(marker in prefix for marker in _INBOUND_MARKERS):
        return "inbound"
    if any(marker in prefix for marker in _OUTBOUND_MARKERS):
        return "outbound"
    return None


def _infer_direction(message: dict[str, Any]) -> Direction:
    if "operatorId" in message:
        return "outbound"
    content = as_dict(message.get("content"))
    if content is not None:
        content_type = content.get("type")
        if isinstance(content_type, str) and content_type.endswith("-reply"):
            return "inbound"
    return "outbound"


def _coerce_direction(value: Any) -> Direction | None:
    if value == "outbound":
        return "outbound"
    if value == "inbound":
        return "inbound"
    return None


def _pairing_errors(entries: list[SessionStateEntry]) -> list[SessionStateError]:
    outbound_ids = {
        e.correlation_id for e in entries if e.direction == "outbound" and e.correlation_id
    }
    errors: list[SessionStateError] = []
    for entry in entries:
        if (
            entry.direction == "inbound"
            and entry.correlation_id
            and entry.correlation_id not in outbound_ids
        ):
            errors.append(
                SessionStateError(
                    f"Inbound response with correlationId {entry.correlation_id!r} "
                    "has no matching outbound request.",
                    index=entry.index,
                )
            )
    return errors


def build_prior_state(entries: tuple[SessionStateEntry, ...]) -> PriorState:
    """Derive stateful context (prior percentages, placement currencies)."""
    state = PriorState()
    for entry in entries:
        if entry.direction != "outbound":
            continue
        content = as_dict(entry.message.get("content"))
        if content is None:
            continue
        _collect_placement_currencies(content, state)
        _collect_cancel_percentage(content, state)
        _collect_cashout_percentage(content, state)
    return state


def _collect_placement_currencies(content: dict[str, Any], state: PriorState) -> None:
    ticket = extract_ticket(content)
    if ticket is None:
        return
    ticket_id = as_str(ticket.get("ticketId"))
    if ticket_id is None:
        return
    currencies = state.placement_currencies.setdefault(ticket_id, set())
    for bet in as_list(ticket.get("bets")):
        if not isinstance(bet, dict):
            continue
        for stake in as_list(bet.get("stake")):
            if isinstance(stake, dict):
                currency = as_str(stake.get("currency"))
                if currency is not None:
                    currencies.add(currency)


def _collect_cancel_percentage(content: dict[str, Any], state: PriorState) -> None:
    cancel = extract_cancel(content)
    if cancel is None:
        return
    _record_percentage(as_dict(cancel.get("details")), state.cancel_percentages)


def _collect_cashout_percentage(content: dict[str, Any], state: PriorState) -> None:
    cashout = extract_cashout(content)
    if cashout is None:
        return
    _record_percentage(as_dict(cashout.get("details")), state.cashout_percentages)


def _record_percentage(
    details: dict[str, Any] | None,
    store: dict[str, list[Decimal]],
) -> None:
    if details is None:
        return
    ticket_id = as_str(details.get("ticketId"))
    value = to_decimal(details.get("percentage"))
    if not ticket_id or value is None:
        return
    store.setdefault(ticket_id, []).append(value)
