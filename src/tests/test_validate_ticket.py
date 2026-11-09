"""Tests for ticket validation."""

from __future__ import annotations

from copy import deepcopy

from mts_client_integration.services.validation import validate_request_payload
from mts_client_integration.tools.validate_ticket import validate_ticket_request

VALID_SINGLE_TICKET: dict[str, object] = {
    "operatorId": "9985",
    "content": {
        "type": "ticket",
        "ticketId": "Ticket_3691",
        "bets": [
            {
                "selections": [
                    {
                        "type": "uf",
                        "productId": "3",
                        "eventId": "sr:match:15050881",
                        "marketId": "1",
                        "outcomeId": "2",
                        "odds": {"type": "decimal", "value": "1.32"},
                    }
                ],
                "stake": [{"type": "cash", "currency": "EUR", "amount": "10"}],
            }
        ],
        "context": {
            "channel": {"type": "internet", "ip": "212.7.5.2", "lang": "EN"},
            "endCustomer": {"id": "user_3454"},
            "limitId": 1409,
        },
    },
    "correlationId": "H293vAko5E",
    "timestampUtc": 1678876155000,
    "operation": "ticket-placement",
    "version": "3.0",
}


def test_valid_single_ticket_passes_schema_and_envelope() -> None:
    result = validate_request_payload(VALID_SINGLE_TICKET)

    assert result.schema_ok is True
    assert result.envelope_ok is True
    assert result.schema_errors == ()
    assert result.envelope_errors == ()


def test_missing_limit_id_fails_schema() -> None:
    payload = deepcopy(VALID_SINGLE_TICKET)
    context = payload["content"]["context"]  # type: ignore[index]
    del context["limitId"]

    result = validate_request_payload(payload)

    assert result.schema_ok is False
    assert any(
        "limitId" in issue.path or "limitId" in issue.message for issue in result.schema_errors
    )


def test_operation_content_mismatch_fails_envelope() -> None:
    payload = {
        **VALID_SINGLE_TICKET,
        "content": {
            "type": "cancel",
            "cancellationId": "cancel-1",
            "details": {
                "type": "ticket",
                "ticketId": "Ticket_3691",
                "code": 103,
            },
        },
    }

    result = validate_request_payload(payload)

    assert result.envelope_ok is False
    assert len(result.envelope_errors) >= 1


def test_operation_parameter_mismatch() -> None:
    result = validate_request_payload(
        VALID_SINGLE_TICKET,
        operation="ticket-cancel",
    )

    assert result.envelope_ok is False
    assert len(result.envelope_errors) == 1
    assert result.envelope_errors[0].rule_id == "operation_mismatch"


def test_invalid_json_string() -> None:
    result = validate_request_payload("not-json")

    assert result.schema_ok is False
    assert result.schema_errors[0].rule_id == "json_parse"


def test_validate_ticket_request_tool_returns_response_dict() -> None:
    result = validate_ticket_request(VALID_SINGLE_TICKET)
    response = result.to_response_dict()

    assert response["schema_ok"] is True
    assert response["envelope_ok"] is True
    assert response["schema_errors"] == []
    assert response["envelope_errors"] == []
