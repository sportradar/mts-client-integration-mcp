"""Golden tests for business-rule and ACK state-machine validation.

Covers partial cash-out cumulative percentage, the cancellation ACK matrix,
predefined systems, and ways/non-SR structure.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mts_client_integration.models.business_rules import PriorState
from mts_client_integration.services.ack_state_machine import evaluate_ack_state_machine
from mts_client_integration.services.business_rules import evaluate_business_rules
from mts_client_integration.services.session_state import parse_session_state
from mts_client_integration.services.validation import validate_request_payload
from tests.factories import bet, single_ticket_envelope, ticket_envelope, uf_selection


def _rule_ids(issues: list[Any]) -> set[str]:
    return {issue.rule_id for issue in issues}


def _severity(issues: list[Any], rule_id: str) -> str | None:
    for issue in issues:
        if issue.rule_id == rule_id:
            return str(issue.severity)
    return None


def _error_rule_ids(issues: list[Any]) -> list[str]:
    return sorted(issue.rule_id for issue in issues if issue.severity == "error")


# --------------------------------------------------------------------------- #
# Payload business rules
# --------------------------------------------------------------------------- #


def _three_uf() -> list[dict[str, Any]]:
    return [uf_selection(f"sr:match:{i}") for i in (1, 2, 3)]


_EXTERNAL_SELECTION = {
    "type": "external",
    "event": "bg:match:9",
    "outcome": "home",
    "odds": {"type": "decimal", "value": "2.0"},
    "expSettleTime": 1678999999000,
}


def test_valid_single_bet_has_no_errors() -> None:
    assert _error_rule_ids(evaluate_business_rules(single_ticket_envelope())) == []


@pytest.mark.parametrize(
    ("bet_node", "rule_id", "severity"),
    [
        pytest.param(
            bet([uf_selection("sr:match:1")], amount="0"),
            "positive_stake",
            "error",
            id="zero-stake",
        ),
        pytest.param(
            bet([uf_selection("sr:match:1", odds="1.00")]),
            "min_odds_1_01",
            "error",
            id="odds-below-1.01",
        ),
        pytest.param(
            bet([uf_selection("sr:match:1")], currency="EURO"),
            "currency_format",
            "error",
            id="four-letter-currency",
        ),
        pytest.param(
            bet(
                [
                    {
                        "type": "accumulator",
                        "selections": [uf_selection(f"sr:match:{i}") for i in range(101)],
                    }
                ]
            ),
            "max_selections_100",
            "error",
            id="101-selections",
        ),
        pytest.param(
            bet([{"type": "system", "size": [2, 3], "selections": _three_uf()}]),
            "predefined_system_sizes",
            "info",
            id="trixie-is-predefined",
        ),
        pytest.param(
            bet([{"type": "system", "size": [5], "selections": _three_uf()}]),
            "system_size_valid",
            "error",
            id="system-size-exceeds-selections",
        ),
        pytest.param(
            bet(
                [
                    {
                        "type": "ways",
                        "selections": [uf_selection("sr:match:1"), uf_selection("sr:match:2")],
                    }
                ]
            ),
            "ways_same_event",
            "error",
            id="ways-across-events",
        ),
        pytest.param(
            bet(
                [
                    {
                        "type": "system",
                        "size": [2],
                        "selections": [*_three_uf()[:2], _EXTERNAL_SELECTION],
                    }
                ]
            ),
            "non_sr_in_system_forbidden",
            "error",
            id="external-selection-in-system",
        ),
        pytest.param(
            bet([uf_selection("sr:match:1", market="1"), uf_selection("sr:match:1", market="2")]),
            "accumulator_no_same_event_without_ways",
            "error",
            id="same-event-accumulator",
        ),
        pytest.param(
            bet(
                [
                    {
                        "type": "uf-custom-bet",
                        "selections": [
                            uf_selection("sr:match:1", odds="2.0"),
                            uf_selection("sr:match:1", market="2", odds="3.0"),
                        ],
                        "odds": {"type": "decimal", "value": "6.0"},
                    }
                ]
            ),
            "custom_bet_odds_not_product",
            "error",
            id="custom-bet-odds-multiplied",
        ),
    ],
)
def test_payload_rule_flagged(bet_node: dict[str, Any], rule_id: str, severity: str) -> None:
    issues = evaluate_business_rules(ticket_envelope([bet_node]))
    assert _severity(issues, rule_id) == severity


def test_frame_size_limit_error_for_huge_payload() -> None:
    issues = evaluate_business_rules(single_ticket_envelope(), serialized_bytes=200_000)
    assert _severity(issues, "frame_size_limit") == "error"


# --------------------------------------------------------------------------- #
# Cash-out cumulative percentage
# --------------------------------------------------------------------------- #


def _cashout_payload(percentage: str, ticket_id: str = "T1") -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "cashout",
            "cashoutId": "co-2",
            "details": {"type": "ticket", "ticketId": ticket_id, "percentage": percentage},
        },
        "correlationId": "corr-c2",
        "timestampUtc": 1678876155000,
        "operation": "ticket-cashout",
        "version": "3.0",
    }


def _prior_with_cashout(percentage: str) -> PriorState:
    state = PriorState()
    state.cashout_percentages["T1"] = [Decimal(percentage)]
    state.placement_currencies["T1"] = {"EUR"}
    return state


def test_partial_cashout_increment_bug_flagged() -> None:
    """After 0.5, sending 0.3 (the increment) violates the cumulative rule."""
    issues = evaluate_business_rules(
        _cashout_payload("0.3"),
        prior_state=_prior_with_cashout("0.5"),
    )
    assert _severity(issues, "cashout_percentage_monotonic") == "error"
    assert "cashout_cumulative_percentage" in _rule_ids(issues)


def test_partial_cashout_cumulative_value_ok() -> None:
    """After 0.5, sending the cumulative 0.8 is accepted (warning only)."""
    issues = evaluate_business_rules(
        _cashout_payload("0.8"),
        prior_state=_prior_with_cashout("0.5"),
    )
    assert _error_rule_ids(issues) == []
    assert _severity(issues, "cashout_cumulative_percentage") == "warning"


def test_cashout_currency_mismatch() -> None:
    payload = _cashout_payload("0.8")
    payload["content"]["details"]["payout"] = [{"amount": "5", "currency": "USD"}]
    issues = evaluate_business_rules(payload, prior_state=_prior_with_cashout("0.5"))
    assert _severity(issues, "cashout_currency_matches_placement") == "error"


# --------------------------------------------------------------------------- #
# ACK / nACK state machine
# --------------------------------------------------------------------------- #


def _out(message: dict[str, Any]) -> dict[str, Any]:
    return {"direction": "outbound", "message": message}


def _in(message: dict[str, Any]) -> dict[str, Any]:
    return {"direction": "inbound", "message": message}


def _ack_issues(session_state: list[dict[str, Any]]) -> list[Any]:
    parsed = parse_session_state(session_state)
    return evaluate_ack_state_machine(parsed.entries)


def _cancel_request(code: int, corr: str = "x1") -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "cancel",
            "cancellationId": "can-1",
            "details": {
                "type": "ticket",
                "ticketId": "T1",
                "ticketSignature": "sig-t",
                "code": code,
            },
        },
        "correlationId": corr,
        "timestampUtc": 1,
        "operation": "ticket-cancel",
        "version": "3.0",
    }


def _cancel_reply(status: str, corr: str = "x1", signature: str = "resp-sig") -> dict[str, Any]:
    return {
        "content": {
            "type": "cancel-reply",
            "cancellationId": "can-1",
            "ticketId": "T1",
            "status": status,
            "code": 0,
            "signature": signature,
        },
        "correlationId": corr,
        "timestampUtc": 2,
        "operation": "ticket-cancel",
        "version": "3.0",
    }


def _cancel_ack(acknowledged: bool, signature: str = "resp-sig") -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "cancel-ack",
            "cancellationId": "can-1",
            "ticketId": "T1",
            "cancellationSignature": signature,
            "acknowledged": acknowledged,
        },
        "correlationId": "x9",
        "timestampUtc": 3,
        "operation": "ticket-cancel-ack",
        "version": "3.0",
    }


def _ticket_reply(status: str, signature: str = "tsig", corr: str = "p1") -> dict[str, Any]:
    return {
        "content": {
            "type": "ticket-reply",
            "ticketId": "T1",
            "status": status,
            "code": 0,
            "signature": signature,
        },
        "correlationId": corr,
        "timestampUtc": 2,
        "operation": "ticket-placement",
        "version": "3.0",
    }


def _ticket_ack(acknowledged: bool, signature: str | None = "tsig") -> dict[str, Any]:
    content: dict[str, Any] = {
        "type": "ticket-ack",
        "ticketId": "T1",
        "acknowledged": acknowledged,
    }
    if signature is not None:
        content["ticketSignature"] = signature
    return {
        "operatorId": "9985",
        "content": content,
        "correlationId": "p9",
        "timestampUtc": 3,
        "operation": "ticket-placement-ack",
        "version": "3.0",
    }


@pytest.mark.parametrize(
    ("session", "rule_id", "severity"),
    [
        pytest.param(
            [_out(_cancel_request(103)), _in(_cancel_reply("accepted"))],
            "cancel_ack_required_101_103_104_105",
            "error",
            id="cancel-103-accepted-without-ack",
        ),
        pytest.param(
            [
                _out(_cancel_request(301)),
                _in(_cancel_reply("accepted")),
                _out(_cancel_ack(True)),
            ],
            "cancel_no_ack_301_302",
            "error",
            id="cancel-301-accepted-but-acked",
        ),
        pytest.param(
            [_out(_cancel_request(103)), _in(_cancel_reply("rejected"))],
            "cancel_nack_on_rejected",
            "error",
            id="cancel-rejected-without-nack",
        ),
        pytest.param(
            [
                _out(_cancel_request(103)),
                _in(_cancel_reply("accepted", signature="A")),
                _out(_cancel_ack(True, signature="B")),
            ],
            "ack_matches_response_signature",
            "error",
            id="cancel-ack-signature-mismatch",
        ),
        pytest.param(
            [_in(_ticket_reply("accepted"))],
            "ticket_ack_on_accepted",
            "info",
            id="ticket-accepted-without-ack",
        ),
        pytest.param(
            [_in(_ticket_reply("accepted")), _out(_ticket_ack(False))],
            "ticket_nack_failed_booking",
            "info",
            id="ticket-accepted-then-nacked",
        ),
        pytest.param(
            [_in(_ticket_reply("rejected")), _out(_ticket_ack(True))],
            "ticket_no_ack_on_rejected",
            "warning",
            id="ticket-rejected-but-acked",
        ),
        pytest.param(
            [_in(_ticket_reply("accepted", signature="A")), _out(_ticket_ack(True, signature="B"))],
            "ack_matches_response_signature",
            "error",
            id="ticket-ack-signature-mismatch",
        ),
        pytest.param(
            [_in(_ticket_reply("accepted")), _out(_ticket_ack(True, signature=None))],
            "ticket_ack_payload_shape",
            "error",
            id="ticket-ack-missing-signature",
        ),
    ],
)
def test_ack_state_machine_flags(
    session: list[dict[str, Any]], rule_id: str, severity: str
) -> None:
    assert _severity(_ack_issues(session), rule_id) == severity


@pytest.mark.parametrize(
    "session",
    [
        pytest.param(
            [
                _out(_cancel_request(103)),
                _in(_cancel_reply("accepted")),
                _out(_cancel_ack(True)),
            ],
            id="cancel-103-accepted-and-acked",
        ),
        pytest.param(
            [_in(_ticket_reply("accepted")), _out(_ticket_ack(True))],
            id="ticket-accepted-and-acked",
        ),
    ],
)
def test_ack_state_machine_correct_flow_has_no_issues(session: list[dict[str, Any]]) -> None:
    assert _ack_issues(session) == []


# --------------------------------------------------------------------------- #
# Cash-out ACK pairing (multiple partial cashouts on one ticket)
# --------------------------------------------------------------------------- #


def _cashout_request(
    cashout_id: str, *, ticket_id: str = "T1", corr: str = "req"
) -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "cashout",
            "cashoutId": cashout_id,
            "details": {
                "type": "ticket-partial",
                "ticketId": ticket_id,
                "ticketSignature": "orig-sig",
                "code": 0,
                "percentage": "0.3",
                "payout": [{"type": "cash", "currency": "EUR", "amount": "5"}],
            },
        },
        "correlationId": corr,
        "timestampUtc": 1,
        "operation": "ticket-cashout",
        "version": "3.0",
    }


def _cashout_reply(
    cashout_id: str,
    *,
    ticket_id: str = "T1",
    signature: str = "sig",
    corr: str = "rep",
) -> dict[str, Any]:
    return {
        "content": {
            "type": "cashout-reply",
            "cashoutId": cashout_id,
            "ticketId": ticket_id,
            "status": "accepted",
            "signature": signature,
        },
        "correlationId": corr,
        "timestampUtc": 2,
        "operation": "ticket-cashout",
        "version": "3.0",
    }


def _cashout_ack(
    cashout_id: str,
    *,
    ticket_id: str = "T1",
    signature: str = "sig",
    corr: str = "ack",
) -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "cashout-ack",
            "cashoutId": cashout_id,
            "ticketId": ticket_id,
            "cashoutSignature": signature,
            "acknowledged": True,
        },
        "correlationId": corr,
        "timestampUtc": 3,
        "operation": "ticket-cashout-ack",
        "version": "3.0",
    }


def test_multiple_partial_cashouts_do_not_pair_wrong_ack() -> None:
    """ACK for cashout co-1 must not match accepted replies for co-2 / co-3 via ticketId."""
    issues = _ack_issues(
        [
            _out(_cashout_request("co-1", corr="req-1")),
            _out(_cashout_request("co-2", corr="req-2")),
            _out(_cashout_request("co-3", corr="req-3")),
            _in(_cashout_reply("co-1", signature="sig-1", corr="rep-1")),
            _out(_cashout_ack("co-1", signature="sig-1", corr="ack-1")),
            _in(_cashout_reply("co-2", signature="sig-2", corr="rep-2")),
            _in(_cashout_reply("co-3", signature="sig-3", corr="rep-3")),
        ]
    )
    assert _error_rule_ids(issues) == []
    # co-2 and co-3 were accepted without their own ACK; only those two get the hint.
    assert [i.rule_id for i in issues] == ["cashout_ack_optional_on_accepted"] * 2


# --------------------------------------------------------------------------- #
# Session-state parsing
# --------------------------------------------------------------------------- #


def test_direction_inference_from_envelope() -> None:
    parsed = parse_session_state(
        [
            _cancel_request(103),  # has operatorId -> outbound
            _cancel_reply("accepted"),  # content.type *-reply -> inbound
        ]
    )
    directions = [entry.direction for entry in parsed.entries]
    assert directions == ["outbound", "inbound"]


def test_log_paste_mode_extracts_and_infers() -> None:
    log = (
        '-> request: {"operatorId":"9985","content":{"type":"cancel",'
        '"cancellationId":"can-1","details":{"type":"ticket","ticketId":"T1",'
        '"ticketSignature":"s","code":103}},"correlationId":"x1",'
        '"timestampUtc":1,"operation":"ticket-cancel","version":"3.0"}\n'
        '<- response: {"content":{"type":"cancel-reply","cancellationId":"can-1",'
        '"ticketId":"T1","status":"accepted","code":0,"signature":"z"},'
        '"correlationId":"x1","timestampUtc":2,"operation":"ticket-cancel","version":"3.0"}'
    )
    parsed = parse_session_state(log)
    assert [e.direction for e in parsed.entries] == ["outbound", "inbound"]
    issues = evaluate_ack_state_machine(parsed.entries)
    assert "cancel_ack_required_101_103_104_105" in _rule_ids(issues)


def test_unmatched_inbound_reported() -> None:
    parsed = parse_session_state([_in(_cancel_reply("accepted", corr="orphan"))])
    assert any("orphan" in err.message for err in parsed.errors)


# --------------------------------------------------------------------------- #
# End-to-end via validate_request_payload
# --------------------------------------------------------------------------- #


def test_end_to_end_cashout_with_session_state() -> None:
    first_cashout = _cashout_payload("0.5")
    result = validate_request_payload(
        _cashout_payload("0.3"),
        session_state=[_out(single_ticket_envelope()), _out(first_cashout)],
    )
    assert result.business_rules_ok is False
    assert "cashout_percentage_monotonic" in _rule_ids(list(result.business_rules))
