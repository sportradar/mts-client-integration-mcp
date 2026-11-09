"""ACK / nACK state-machine validation over the session state.

Implements MVP capability #2's ack-flow layer. Everything is derived from raw
envelopes (see the external DTOs): inbound response ``status``/``code``/
``signature`` are paired by ``correlationId`` with the originating outbound
request (to recover the cancellation code) and with any subsequent outbound ACK
(matched by ``cancellationId``/``cashoutId``/``ticketId``). The cancellation ACK
cancellation ACK matrix is:

* codes 101/103/104/105 accepted  -> ACK required (``acknowledged: true``)
* codes 301/302 accepted          -> no ACK may be sent
* rejected                        -> nACK required (``acknowledged: false``)

Ticket-placement acknowledgement (``ticket-reply`` -> ``ticket-ack``) is
config-gated (only mandatory when ticket acknowledgement is enabled), so its
presence rules are surfaced as ``info`` rather than ``error``:

* accepted ticket  -> if enabled, ACK with ``acknowledged: true``; a nACK
  (``acknowledged: false``) tells MTS you could not book it and it is auto-cancelled
* rejected ticket  -> nothing to acknowledge (a stray ACK is a ``warning``)

ACK payload shapes and signature matching are always validated when an ACK is
present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from mts_client_integration.models.business_rules import (
    CANCEL_CODES_ACK_REQUIRED,
    CANCEL_CODES_NO_ACK,
    AckIssue,
    SessionStateEntry,
)
from mts_client_integration.services.ticket_tree import as_dict, as_str

AckFamily = Literal["ticket", "cancel", "cashout"]

_TICKET_REPLY_TYPES = frozenset({"ticket-reply"})
_CANCEL_REPLY_TYPES = frozenset({"cancel-reply"})
_CASHOUT_REPLY_TYPES = frozenset(
    {
        "cashout-reply",
        "cashout-inform-reply",
        "cashout-build-reply",
        "cashout-placement-reply",
    }
)
_ACK_FAMILY_BY_TYPE: dict[str, AckFamily] = {
    "ticket-ack": "ticket",
    "cancel-ack": "cancel",
    "cashout-ack": "cashout",
    "cashout-inform-ack": "cashout",
    "cashout-placement-ack": "cashout",
}
_ACK_SHAPE_RULE: dict[AckFamily, str] = {
    "ticket": "ticket_ack_payload_shape",
    "cancel": "cancel_ack_payload_shape",
    "cashout": "cashout_ack_payload_shape",
}


@dataclass(frozen=True)
class Ack:
    """An outbound ACK / nACK message (or the payload being validated)."""

    family: AckFamily
    content_type: str
    correlation_id: str | None
    ticket_id: str | None
    cancellation_id: str | None
    cashout_id: str | None
    acknowledged: object
    ticket_signature: str | None
    cancellation_signature: str | None
    cashout_signature: str | None

    @property
    def shape_rule_id(self) -> str:
        return _ACK_SHAPE_RULE[self.family]

    @property
    def primary_id(self) -> str | None:
        """The id that pairs this ACK with its response, depending on the family."""
        if self.family == "cancel":
            return self.cancellation_id
        if self.family == "cashout":
            return self.cashout_id
        return self.ticket_id

    @property
    def signature(self) -> str | None:
        """The response signature this ACK echoes, depending on the family."""
        if self.family == "cancel":
            return self.cancellation_signature
        if self.family == "cashout":
            return self.cashout_signature
        return self.ticket_signature


def evaluate_ack_state_machine(
    entries: tuple[SessionStateEntry, ...],
    *,
    current_payload: dict[str, Any] | None = None,
) -> list[AckIssue]:
    """Evaluate the ACK/nACK matrix and ACK payload shapes."""
    outbound = [e for e in entries if e.direction == "outbound"]
    inbound = [e for e in entries if e.direction == "inbound"]
    requests_by_corr: dict[str, SessionStateEntry] = {
        e.correlation_id: e for e in outbound if e.correlation_id
    }

    acks = _collect_acks(outbound)
    current = _as_current_ack(current_payload)
    if current is not None:
        acks.append(current)

    issues: list[AckIssue] = []
    issues.extend(_check_ack_shapes(acks))
    issues.extend(_check_timeouts(outbound, inbound))
    for reply in inbound:
        content = as_dict(reply.message.get("content"))
        if content is None:
            continue
        reply_type = content.get("type")
        if reply_type in _TICKET_REPLY_TYPES:
            issues.extend(_check_ticket_reply(reply, content, acks))
        elif reply_type in _CANCEL_REPLY_TYPES:
            issues.extend(_check_cancel_reply(reply, content, requests_by_corr, acks))
        elif reply_type in _CASHOUT_REPLY_TYPES:
            issues.extend(_check_cashout_reply(reply, content, acks))
    return issues


def _collect_acks(outbound: list[SessionStateEntry]) -> list[Ack]:
    acks: list[Ack] = []
    for entry in outbound:
        ack = _as_ack(entry.message, entry.correlation_id)
        if ack is not None:
            acks.append(ack)
    return acks


def _as_current_ack(payload: dict[str, Any] | None) -> Ack | None:
    if payload is None:
        return None
    return _as_ack(payload, as_str(payload.get("correlationId")))


def _as_ack(message: dict[str, Any], correlation_id: str | None) -> Ack | None:
    content = as_dict(message.get("content"))
    if content is None:
        return None
    content_type = content.get("type")
    family = _ACK_FAMILY_BY_TYPE.get(content_type) if isinstance(content_type, str) else None
    if family is None or not isinstance(content_type, str):
        return None
    return Ack(
        family=family,
        content_type=content_type,
        correlation_id=correlation_id,
        ticket_id=as_str(content.get("ticketId")),
        cancellation_id=as_str(content.get("cancellationId")),
        cashout_id=as_str(content.get("cashoutId")),
        acknowledged=content.get("acknowledged"),
        ticket_signature=as_str(content.get("ticketSignature")),
        cancellation_signature=as_str(content.get("cancellationSignature")),
        cashout_signature=as_str(content.get("cashoutSignature")),
    )


def _check_ack_shapes(acks: list[Ack]) -> list[AckIssue]:
    issues: list[AckIssue] = []
    for ack in acks:
        rule = ack.shape_rule_id

        def issue(message: str, rule: str = rule, ack: Ack = ack) -> AckIssue:
            return AckIssue(rule, "error", message, ack.correlation_id, ack.ticket_id)

        if not isinstance(ack.acknowledged, bool):
            issues.append(issue(f"{ack.content_type} is missing a boolean 'acknowledged' field."))
        if ack.family == "ticket" and not ack.ticket_id:
            issues.append(issue("ticket-ack is missing 'ticketId'."))
        if ack.family == "ticket" and not ack.ticket_signature:
            issues.append(issue("ticket-ack is missing 'ticketSignature'."))
        if ack.family == "cancel" and not ack.cancellation_id:
            issues.append(issue("cancel-ack is missing 'cancellationId'."))
        if ack.family == "cashout" and not (ack.cashout_id or ack.ticket_id):
            issues.append(issue("cashout-ack is missing both 'cashoutId' and 'ticketId'."))
    return issues


def _check_timeouts(
    outbound: list[SessionStateEntry],
    inbound: list[SessionStateEntry],
) -> list[AckIssue]:
    replied = {e.correlation_id for e in inbound if e.correlation_id}
    issues: list[AckIssue] = []
    for entry in outbound:
        if entry.operation != "ticket-cancel":
            continue
        if entry.correlation_id and entry.correlation_id not in replied:
            issues.append(
                AckIssue(
                    "cancel_no_ack_on_timeout",
                    "info",
                    "Cancellation request received no MTS response; flag this ticket in "
                    "your DB for OAM review.",
                    entry.correlation_id,
                )
            )
    return issues


def _check_ticket_reply(
    reply: SessionStateEntry,
    content: dict[str, Any],
    acks: list[Ack],
) -> list[AckIssue]:
    status = content.get("status")
    ticket_id = as_str(content.get("ticketId"))
    matching = _find_ack(acks, "ticket", ticket_id, ticket_id)

    if status == "rejected":
        if matching is not None:
            return [
                AckIssue(
                    "ticket_no_ack_on_rejected",
                    "warning",
                    "Rejected ticket was not placed and should not be acknowledged.",
                    reply.correlation_id,
                    ticket_id,
                )
            ]
        return []

    if matching is None:
        return [
            AckIssue(
                "ticket_ack_on_accepted",
                "info",
                "If ticket acknowledgement is enabled, an accepted ticket must be "
                "ACKed with acknowledged=true (send acknowledged=false to signal you "
                "could not book it).",
                reply.correlation_id,
                ticket_id,
            )
        ]

    issues: list[AckIssue] = []
    if matching.acknowledged is False:
        issues.append(
            AckIssue(
                "ticket_nack_failed_booking",
                "info",
                "nACK (acknowledged=false) on an accepted ticket tells MTS you could "
                "not book it; MTS will treat the ticket as not placed.",
                reply.correlation_id,
                ticket_id,
            )
        )
    issues.extend(
        _check_signature(matching, content_signature(reply), reply.correlation_id, ticket_id)
    )
    return issues


def _check_cancel_reply(
    reply: SessionStateEntry,
    content: dict[str, Any],
    requests_by_corr: dict[str, SessionStateEntry],
    acks: list[Ack],
) -> list[AckIssue]:
    status = content.get("status")
    cancellation_id = as_str(content.get("cancellationId"))
    ticket_id = as_str(content.get("ticketId"))
    matching = _find_ack(acks, "cancel", cancellation_id, ticket_id)

    if status == "rejected":
        return _expect_nack(reply, matching, ticket_id)

    code = _cancel_code_for(reply, requests_by_corr)
    if code in CANCEL_CODES_ACK_REQUIRED:
        return _expect_ack(reply, matching, code, ticket_id)
    if code in CANCEL_CODES_NO_ACK:
        return _expect_no_ack(reply, matching, code, ticket_id)
    return []


def _expect_nack(
    reply: SessionStateEntry,
    matching: Ack | None,
    ticket_id: str | None,
) -> list[AckIssue]:
    if matching is None:
        return [
            AckIssue(
                "cancel_nack_on_rejected",
                "error",
                "Rejected cancellation requires a nACK (cancel-ack with "
                "acknowledged=false); none found.",
                reply.correlation_id,
                ticket_id,
            )
        ]
    if matching.acknowledged is not False:
        return [
            AckIssue(
                "cancel_nack_on_rejected",
                "error",
                "Rejected cancellation must be nACKed with acknowledged=false.",
                reply.correlation_id,
                ticket_id,
            )
        ]
    return _check_signature(matching, content_signature(reply), reply.correlation_id, ticket_id)


def _expect_ack(
    reply: SessionStateEntry,
    matching: Ack | None,
    code: int,
    ticket_id: str | None,
) -> list[AckIssue]:
    if matching is None:
        return [
            AckIssue(
                "cancel_ack_required_101_103_104_105",
                "error",
                f"Accepted cancellation (code {code}) requires a cancel-ack with "
                "acknowledged=true; none found.",
                reply.correlation_id,
                ticket_id,
            )
        ]
    if matching.acknowledged is not True:
        return [
            AckIssue(
                "cancel_ack_required_101_103_104_105",
                "error",
                f"Accepted cancellation (code {code}) must be ACKed with acknowledged=true.",
                reply.correlation_id,
                ticket_id,
            )
        ]
    return _check_signature(matching, content_signature(reply), reply.correlation_id, ticket_id)


def _expect_no_ack(
    reply: SessionStateEntry,
    matching: Ack | None,
    code: int,
    ticket_id: str | None,
) -> list[AckIssue]:
    if matching is not None:
        return [
            AckIssue(
                "cancel_no_ack_301_302",
                "error",
                f"Cancellation code {code} must NOT be acknowledged, but an ACK was sent.",
                reply.correlation_id,
                ticket_id,
            )
        ]
    return []


def _check_cashout_reply(
    reply: SessionStateEntry,
    content: dict[str, Any],
    acks: list[Ack],
) -> list[AckIssue]:
    status = content.get("status")
    cashout_id = as_str(content.get("cashoutId"))
    ticket_id = as_str(content.get("ticketId"))
    matching = _find_ack(acks, "cashout", cashout_id, ticket_id)
    if status == "rejected":
        if matching is not None:
            return [
                AckIssue(
                    "cashout_no_ack_on_declined",
                    "warning",
                    "Declined cash-out should not be ACKed; flag it in your DB for OAM instead.",
                    reply.correlation_id,
                    ticket_id,
                )
            ]
        return [
            AckIssue(
                "cashout_no_ack_on_declined",
                "info",
                "Cash-out was declined; ensure the ticket is flagged in your DB for OAM review.",
                reply.correlation_id,
                ticket_id,
            )
        ]
    if matching is not None:
        return _check_signature(matching, content_signature(reply), reply.correlation_id, ticket_id)
    return [
        AckIssue(
            "cashout_ack_optional_on_accepted",
            "info",
            "Accepted cash-out may optionally be ACKed.",
            reply.correlation_id,
            ticket_id,
        )
    ]


def _check_signature(
    ack: Ack,
    reply_signature: str | None,
    correlation_id: str | None,
    ticket_id: str | None,
) -> list[AckIssue]:
    if reply_signature and ack.signature and reply_signature != ack.signature:
        return [
            AckIssue(
                "ack_matches_response_signature",
                "error",
                "ACK signature does not match the paired response signature.",
                correlation_id,
                ticket_id,
            )
        ]
    return []


def _cancel_code_for(
    reply: SessionStateEntry,
    requests_by_corr: dict[str, SessionStateEntry],
) -> int | None:
    request = requests_by_corr.get(reply.correlation_id) if reply.correlation_id else None
    if request is None:
        return None
    content = as_dict(request.message.get("content"))
    if content is None:
        return None
    details = as_dict(content.get("details"))
    if details is None:
        return None
    code = details.get("code")
    return code if isinstance(code, int) and not isinstance(code, bool) else None


def _find_ack(
    acks: list[Ack],
    family: AckFamily,
    primary_id: str | None,
    ticket_id: str | None,
) -> Ack | None:
    family_acks = [ack for ack in acks if ack.family == family]
    if primary_id:
        for ack in family_acks:
            if ack.primary_id == primary_id:
                return ack
    if ticket_id:
        for ack in family_acks:
            if ack.ticket_id == ticket_id:
                return ack
    return None


def content_signature(entry: SessionStateEntry) -> str | None:
    content = as_dict(entry.message.get("content"))
    if content is None:
        return None
    return as_str(content.get("signature"))
