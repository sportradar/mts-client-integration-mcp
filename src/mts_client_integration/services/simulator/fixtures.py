"""Fixture response builders for the local MTS simulator."""

from __future__ import annotations

import time
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from mts_client_integration.services.ticket_tree import as_dict


def _now_ms() -> int:
    return int(time.time() * 1000)


def request_ticket_id(envelope: dict[str, Any]) -> str | None:
    """Return ``ticketId`` from ``content`` (placement) or ``content.details`` (cancel/cashout)."""
    content = as_dict(envelope.get("content")) or {}
    details = as_dict(content.get("details")) or {}
    for source in (content, details):
        ticket_id = source.get("ticketId")
        if isinstance(ticket_id, str):
            return ticket_id
    return None


def _ticket_id_from_request(envelope: dict[str, Any]) -> str:
    return request_ticket_id(envelope) or f"mock-{uuid.uuid4().hex[:12]}"


def _correlation_id(envelope: dict[str, Any]) -> str:
    corr = envelope.get("correlationId")
    return corr if isinstance(corr, str) else uuid.uuid4().hex


def build_ticket_accepted(
    envelope: dict[str, Any],
    *,
    signature: str | None = None,
) -> dict[str, Any]:
    ticket_id = _ticket_id_from_request(envelope)
    sig = signature or f"mock-sig-{uuid.uuid4().hex[:16]}"
    content = envelope.get("content")
    bets = content.get("bets", []) if isinstance(content, dict) else []
    bet_details: list[dict[str, Any]] = []
    if isinstance(bets, list) and bets:
        bet_details.append(
            {
                "code": 0,
                "message": "Transaction processed",
                "betId": f"{ticket_id}-0",
                "selectionDetails": [],
            }
        )
    return {
        "content": {
            "type": "ticket-reply",
            "message": "Ticket accepted",
            "code": 0,
            "signature": sig,
            "ticketId": ticket_id,
            "status": "accepted",
            "betDetails": bet_details,
            "exchangeRate": [{"fromCurrency": "EUR", "toCurrency": "EUR", "rate": "1.0"}],
        },
        "correlationId": _correlation_id(envelope),
        "timestampUtc": _now_ms(),
        "operation": "ticket-placement",
        "version": "3.0",
    }


def build_ticket_rejected(
    envelope: dict[str, Any],
    *,
    code: int = -702,
    message: str = "Bet liability exceeded",
    signature: str | None = None,
    alt_stake: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ticket_id = _ticket_id_from_request(envelope)
    sig = signature or f"mock-sig-{uuid.uuid4().hex[:16]}"
    content: dict[str, Any] = {
        "type": "ticket-reply",
        "message": message,
        "code": code,
        "signature": sig,
        "ticketId": ticket_id,
        "status": "rejected",
    }
    if alt_stake is not None:
        content["altStake"] = alt_stake
    return {
        "content": content,
        "correlationId": _correlation_id(envelope),
        "timestampUtc": _now_ms(),
        "operation": "ticket-placement",
        "version": "3.0",
    }


def build_rate_limit_rejection(envelope: dict[str, Any]) -> dict[str, Any]:
    return build_ticket_rejected(
        envelope,
        code=-999,
        message="Rate limit exceeded (fixture-driven mock)",
    )


def build_cancel_reply(
    envelope: dict[str, Any],
    *,
    accepted: bool,
    signature: str | None = None,
) -> dict[str, Any]:
    content_in = as_dict(envelope.get("content")) or {}
    ticket_id = request_ticket_id(envelope) or ""
    cancellation_id = content_in.get("cancellationId")
    cancel_id = cancellation_id if isinstance(cancellation_id, str) else ticket_id
    sig = signature or f"mock-cancel-{uuid.uuid4().hex[:12]}"
    return {
        "content": {
            "type": "cancel-reply",
            "message": "Cancellation accepted" if accepted else "Cancellation rejected",
            "code": 0 if accepted else -103,
            "signature": sig,
            "ticketId": ticket_id,
            "cancellationId": cancel_id,
            "status": "accepted" if accepted else "rejected",
        },
        "correlationId": _correlation_id(envelope),
        "timestampUtc": _now_ms(),
        "operation": "ticket-cancel",
        "version": "3.0",
    }


def build_cashout_reply(
    envelope: dict[str, Any],
    *,
    accepted: bool,
    code: int = 0,
    message: str = "Cashout accepted",
) -> dict[str, Any]:
    content_in = as_dict(envelope.get("content")) or {}
    ticket_id = request_ticket_id(envelope) or ""
    requested_cashout_id = content_in.get("cashoutId")
    cashout_id = requested_cashout_id if isinstance(requested_cashout_id, str) else ticket_id
    return {
        "content": {
            "type": "cashout-reply",
            "message": message if accepted else "Cashout rejected",
            "code": code if accepted else -1,
            "ticketId": ticket_id,
            "cashoutId": cashout_id,
            "status": "accepted" if accepted else "rejected",
        },
        "correlationId": _correlation_id(envelope),
        "timestampUtc": _now_ms(),
        "operation": "ticket-cashout",
        "version": "3.0",
    }


def default_alt_stake_amount(envelope: dict[str, Any]) -> dict[str, str]:
    content = envelope.get("content")
    currency = "EUR"
    if isinstance(content, dict):
        bets = content.get("bets")
        if isinstance(bets, list) and bets:
            stakes = bets[0].get("stake") if isinstance(bets[0], dict) else None
            if isinstance(stakes, list) and stakes:
                stake0 = stakes[0]
                if isinstance(stake0, dict) and isinstance(stake0.get("currency"), str):
                    currency = stake0["currency"]
    return {"type": "cash", "currency": currency, "amount": "5.00"}


def parse_cashout_percentage(envelope: dict[str, Any]) -> Decimal | None:
    content = envelope.get("content")
    if not isinstance(content, dict):
        return None
    raw = content.get("percentage")
    if raw is None:
        details = content.get("details")
        if isinstance(details, dict):
            raw = details.get("percentage")
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None
