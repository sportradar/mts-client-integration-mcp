"""Golden tests for business-rule and ACK state-machine validation.

Covers partial cash-out cumulative percentage, the cancellation ACK matrix,
predefined systems, and ways/non-SR structure.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mts_client_integration.models.business_rules import PriorState
from mts_client_integration.services.ack_state_machine import evaluate_ack_state_machine
from mts_client_integration.services.business_rules import evaluate_business_rules
from mts_client_integration.services.session_state import parse_session_state
from mts_client_integration.services.validation import validate_request_payload


def _rule_ids(issues: list[Any]) -> set[str]:
    return {issue.rule_id for issue in issues}


def _severity(issues: list[Any], rule_id: str) -> str | None:
    for issue in issues:
        if issue.rule_id == rule_id:
            return str(issue.severity)
    return None


# --------------------------------------------------------------------------- #
# Payload business rules
# --------------------------------------------------------------------------- #


def _ticket(bets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "ticket",
            "ticketId": "T1",
            "bets": bets,
            "context": {
                "channel": {"type": "internet", "ip": "1.2.3.4", "lang": "en"},
                "endCustomer": {"id": "user1"},
                "limitId": 1,
            },
        },
        "correlationId": "corr-1",
        "timestampUtc": 1678876155000,
        "operation": "ticket-placement",
        "version": "3.0",
    }


def _uf(event: str, market: str = "1", outcome: str = "1", odds: str = "1.5") -> dict[str, Any]:
    return {
        "type": "uf",
        "productId": "3",
        "eventId": event,
        "marketId": market,
        "outcomeId": outcome,
        "odds": {"type": "decimal", "value": odds},
    }


def _bet(selections: list[dict[str, Any]], amount: str = "10") -> dict[str, Any]:
    return {
        "selections": selections,
        "stake": [{"type": "cash", "currency": "EUR", "amount": amount}],
    }


def test_positive_stake_and_min_odds() -> None:
    bet = _bet([_uf("sr:match:1", odds="1.00")], amount="0")
    issues = evaluate_business_rules(_ticket([bet]))
    ids = _rule_ids(issues)
    assert "positive_stake" in ids
    assert "min_odds_1_01" in ids


def test_bad_currency_flagged() -> None:
    bet = _bet([_uf("sr:match:1")])
    bet["stake"][0]["currency"] = "EURO"
    issues = evaluate_business_rules(_ticket([bet]))
    assert "currency_format" in _rule_ids(issues)


def test_selection_cap_exceeded() -> None:
    selections = [_uf(f"sr:match:{i}") for i in range(101)]
    bet = _bet([{"type": "accumulator", "selections": selections}])
    issues = evaluate_business_rules(_ticket([bet]))
    assert "max_selections_100" in _rule_ids(issues)


def test_predefined_system_trixie_is_info() -> None:
    system = {
        "type": "system",
        "size": [2, 3],
        "selections": [_uf("sr:match:1"), _uf("sr:match:2"), _uf("sr:match:3")],
    }
    issues = evaluate_business_rules(_ticket([_bet([system])]))
    assert _severity(issues, "predefined_system_sizes") == "info"


def test_system_size_out_of_range_is_error() -> None:
    system = {
        "type": "system",
        "size": [5],
        "selections": [_uf("sr:match:1"), _uf("sr:match:2"), _uf("sr:match:3")],
    }
    issues = evaluate_business_rules(_ticket([_bet([system])]))
    assert _severity(issues, "system_size_valid") == "error"


def test_ways_must_share_event() -> None:
    ways = {"type": "ways", "selections": [_uf("sr:match:1"), _uf("sr:match:2")]}
    issues = evaluate_business_rules(_ticket([_bet([ways])]))
    assert _severity(issues, "ways_same_event") == "error"


def test_non_sr_in_system_forbidden() -> None:
    external = {
        "type": "external",
        "event": "bg:match:9",
        "outcome": "home",
        "odds": {"type": "decimal", "value": "2.0"},
        "expSettleTime": 1678999999000,
    }
    system = {
        "type": "system",
        "size": [2],
        "selections": [_uf("sr:match:1"), _uf("sr:match:2"), external],
    }
    issues = evaluate_business_rules(_ticket([_bet([system])]))
    assert _severity(issues, "non_sr_in_system_forbidden") == "error"


def test_same_event_accumulator_requires_ways() -> None:
    bet = _bet([_uf("sr:match:1", market="1"), _uf("sr:match:1", market="2")])
    issues = evaluate_business_rules(_ticket([bet]))
    assert "accumulator_no_same_event_without_ways" in _rule_ids(issues)


def test_custom_bet_odds_must_not_be_product() -> None:
    inner = [_uf("sr:match:1", odds="2.0"), _uf("sr:match:1", market="2", odds="3.0")]
    custom = {
        "type": "uf-custom-bet",
        "selections": inner,
        "odds": {"type": "decimal", "value": "6.0"},
    }
    issues = evaluate_business_rules(_ticket([_bet([custom])]))
    assert _severity(issues, "custom_bet_odds_not_product") == "error"


def test_frame_size_limit_error_for_huge_payload() -> None:
    issues = evaluate_business_rules(_ticket([_bet([_uf("sr:match:1")])]), serialized_bytes=200_000)
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
    ids = _rule_ids(issues)
    assert "cashout_percentage_monotonic" in ids
    assert _severity(issues, "cashout_percentage_monotonic") == "error"
    assert "cashout_cumulative_percentage" in ids


def test_partial_cashout_cumulative_value_ok() -> None:
    """After 0.5, sending the cumulative 0.8 is accepted (warning only)."""
    issues = evaluate_business_rules(
        _cashout_payload("0.8"),
        prior_state=_prior_with_cashout("0.5"),
    )
    assert "cashout_percentage_monotonic" not in _rule_ids(issues)
    assert _severity(issues, "cashout_cumulative_percentage") == "warning"


def test_cashout_currency_mismatch() -> None:
    payload = _cashout_payload("0.8")
    payload["content"]["details"]["payout"] = [{"amount": "5", "currency": "USD"}]
    issues = evaluate_business_rules(payload, prior_state=_prior_with_cashout("0.5"))
    assert _severity(issues, "cashout_currency_matches_placement") == "error"


# --------------------------------------------------------------------------- #
# Cancellation ACK matrix
# --------------------------------------------------------------------------- #


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


def _ack_issues(session_state: list[dict[str, Any]]) -> list[Any]:
    parsed = parse_session_state(session_state)
    return evaluate_ack_state_machine(parsed.entries)


def test_accepted_cancel_103_requires_ack() -> None:
    issues = _ack_issues(
        [
            {"direction": "outbound", "message": _cancel_request(103)},
            {"direction": "inbound", "message": _cancel_reply("accepted")},
        ]
    )
    assert "cancel_ack_required_101_103_104_105" in _rule_ids(issues)


def test_accepted_cancel_103_with_ack_passes() -> None:
    issues = _ack_issues(
        [
            {"direction": "outbound", "message": _cancel_request(103)},
            {"direction": "inbound", "message": _cancel_reply("accepted")},
            {"direction": "outbound", "message": _cancel_ack(True)},
        ]
    )
    assert "cancel_ack_required_101_103_104_105" not in _rule_ids(issues)


def test_accepted_cancel_301_must_not_ack() -> None:
    issues = _ack_issues(
        [
            {"direction": "outbound", "message": _cancel_request(301)},
            {"direction": "inbound", "message": _cancel_reply("accepted")},
            {"direction": "outbound", "message": _cancel_ack(True)},
        ]
    )
    assert _severity(issues, "cancel_no_ack_301_302") == "error"


def test_rejected_cancel_requires_nack() -> None:
    issues = _ack_issues(
        [
            {"direction": "outbound", "message": _cancel_request(103)},
            {"direction": "inbound", "message": _cancel_reply("rejected")},
        ]
    )
    assert "cancel_nack_on_rejected" in _rule_ids(issues)


def test_ack_signature_mismatch_detected() -> None:
    issues = _ack_issues(
        [
            {"direction": "outbound", "message": _cancel_request(103)},
            {"direction": "inbound", "message": _cancel_reply("accepted", signature="A")},
            {"direction": "outbound", "message": _cancel_ack(True, signature="B")},
        ]
    )
    assert "ack_matches_response_signature" in _rule_ids(issues)


# --------------------------------------------------------------------------- #
# Ticket-placement ACK (ticket-reply -> ticket-ack)
# --------------------------------------------------------------------------- #


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


def _ticket_ack(acknowledged: bool, signature: str = "tsig") -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "ticket-ack",
            "ticketId": "T1",
            "ticketSignature": signature,
            "acknowledged": acknowledged,
        },
        "correlationId": "p9",
        "timestampUtc": 3,
        "operation": "ticket-placement-ack",
        "version": "3.0",
    }


def test_accepted_ticket_without_ack_is_info() -> None:
    issues = _ack_issues(
        [
            {"direction": "inbound", "message": _ticket_reply("accepted")},
        ]
    )
    assert _severity(issues, "ticket_ack_on_accepted") == "info"


def test_accepted_ticket_with_ack_passes() -> None:
    issues = _ack_issues(
        [
            {"direction": "inbound", "message": _ticket_reply("accepted")},
            {"direction": "outbound", "message": _ticket_ack(True)},
        ]
    )
    ids = _rule_ids(issues)
    assert "ticket_ack_on_accepted" not in ids
    assert "ack_matches_response_signature" not in ids


def test_accepted_ticket_nack_signals_failed_booking() -> None:
    issues = _ack_issues(
        [
            {"direction": "inbound", "message": _ticket_reply("accepted")},
            {"direction": "outbound", "message": _ticket_ack(False)},
        ]
    )
    assert _severity(issues, "ticket_nack_failed_booking") == "info"


def test_rejected_ticket_should_not_be_acked() -> None:
    issues = _ack_issues(
        [
            {"direction": "inbound", "message": _ticket_reply("rejected")},
            {"direction": "outbound", "message": _ticket_ack(True)},
        ]
    )
    assert _severity(issues, "ticket_no_ack_on_rejected") == "warning"


def test_ticket_ack_signature_mismatch_detected() -> None:
    issues = _ack_issues(
        [
            {"direction": "inbound", "message": _ticket_reply("accepted", signature="A")},
            {"direction": "outbound", "message": _ticket_ack(True, signature="B")},
        ]
    )
    assert "ack_matches_response_signature" in _rule_ids(issues)


def test_ticket_ack_missing_signature_is_shape_error() -> None:
    bad_ack = _ticket_ack(True)
    del bad_ack["content"]["ticketSignature"]
    issues = _ack_issues(
        [
            {"direction": "inbound", "message": _ticket_reply("accepted")},
            {"direction": "outbound", "message": bad_ack},
        ]
    )
    assert _severity(issues, "ticket_ack_payload_shape") == "error"


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
    parsed = parse_session_state(
        [
            {"direction": "inbound", "message": _cancel_reply("accepted", corr="orphan")},
        ]
    )
    assert any("orphan" in err.message for err in parsed.errors)


# --------------------------------------------------------------------------- #
# End-to-end via validate_request_payload
# --------------------------------------------------------------------------- #


def test_end_to_end_cashout_with_session_state() -> None:
    placement = _ticket([_bet([_uf("sr:match:1")])])
    first_cashout = _cashout_payload("0.5")
    result = validate_request_payload(
        _cashout_payload("0.3"),
        session_state=[
            {"direction": "outbound", "message": placement},
            {"direction": "outbound", "message": first_cashout},
        ],
    )
    assert result.business_rules_ok is False
    assert "cashout_percentage_monotonic" in _rule_ids(list(result.business_rules))
