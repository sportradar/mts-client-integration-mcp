"""Tests for ticket validation."""

from __future__ import annotations

from typing import Any

import pytest

from mts_client_integration.services.validation import validate_request_payload
from tests.factories import single_ticket_envelope


def _without_limit_id() -> dict[str, Any]:
    payload = single_ticket_envelope()
    del payload["content"]["context"]["limitId"]
    return payload


def _cancel_content_under_placement_operation() -> dict[str, Any]:
    return {
        **single_ticket_envelope(),
        "content": {
            "type": "cancel",
            "cancellationId": "cancel-1",
            "details": {"type": "ticket", "ticketId": "T1", "code": 103},
        },
    }


def test_valid_single_ticket_passes_all_layers() -> None:
    result = validate_request_payload(single_ticket_envelope())

    assert result.schema_ok is True
    assert result.envelope_ok is True
    assert result.business_rules_ok is True
    assert result.ack_state_machine_ok is True
    assert result.schema_errors == ()
    assert result.envelope_errors == ()


@pytest.mark.parametrize(
    ("payload", "operation", "expected_rule_ids"),
    [
        pytest.param("not-json", None, ["json_parse"], id="invalid-json"),
        pytest.param(_without_limit_id(), None, ["jsonschema"], id="missing-limit-id"),
    ],
)
def test_schema_failures(
    payload: dict[str, Any] | str, operation: str | None, expected_rule_ids: list[str]
) -> None:
    result = validate_request_payload(payload, operation=operation)

    assert result.schema_ok is False
    assert [issue.rule_id for issue in result.schema_errors] == expected_rule_ids


def test_missing_limit_id_points_at_context() -> None:
    (issue,) = validate_request_payload(_without_limit_id()).schema_errors

    assert issue.path == "$.content.context"
    assert "limitId" in issue.message


@pytest.mark.parametrize(
    ("payload", "operation", "expected_rule_id"),
    [
        pytest.param(
            single_ticket_envelope(),
            "ticket-cancel",
            "operation_mismatch",
            id="operation-argument-differs-from-payload",
        ),
        pytest.param(
            _cancel_content_under_placement_operation(),
            None,
            "envelope",
            id="content-type-differs-from-operation",
        ),
    ],
)
def test_envelope_failures(
    payload: dict[str, Any], operation: str | None, expected_rule_id: str
) -> None:
    result = validate_request_payload(payload, operation=operation)

    assert result.envelope_ok is False
    assert [issue.rule_id for issue in result.envelope_errors] == [expected_rule_id]


def test_to_response_dict_serializes_issue_lists() -> None:
    response = validate_request_payload(single_ticket_envelope()).to_response_dict()

    assert response["schema_ok"] is True
    assert response["envelope_ok"] is True
    assert response["schema_errors"] == []
    assert response["envelope_errors"] == []
