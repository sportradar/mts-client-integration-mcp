"""Ticket 3.0 request validation orchestration."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from mts_client_integration.models.ticket3._generated import Operation
from mts_client_integration.models.ticket3.operations import OPERATION_TO_CONTENT_TYPE
from mts_client_integration.models.ticket3.request import Request
from mts_client_integration.models.ticket3.validator import RequestValidator
from mts_client_integration.models.validation import ValidationIssue, ValidationResult
from mts_client_integration.services.ack_state_machine import evaluate_ack_state_machine
from mts_client_integration.services.business_rules import evaluate_business_rules
from mts_client_integration.services.envelope_errors import envelope_issues
from mts_client_integration.services.schema_errors import schema_issues
from mts_client_integration.services.session_state import build_prior_state, parse_session_state


def validate_request_payload(
    payload: object | str,
    *,
    operation: str | None = None,
    validator: RequestValidator | None = None,
    session_state: object | None = None,
    reference_time_utc_ms: int | None = None,
    serialized_bytes: int | None = None,
) -> ValidationResult:
    """Validate a Ticket 3.0 request across all four validation layers.

    Runs JSON Schema validation, Pydantic envelope parsing (including the
    ``operation`` ↔ ``content.type`` consistency check), business-rule checks,
    and the ACK/nACK state machine derived from the optional ``session_state``.
    """
    instance, parse_errors = _normalize_payload(payload)
    session_state_result = parse_session_state(session_state)
    session_state_errors = list(session_state_result.errors)
    prior_state = build_prior_state(session_state_result.entries)

    if parse_errors:
        return ValidationResult.from_issues(
            schema_errors=parse_errors,
            envelope_errors=[],
            session_state_errors=session_state_errors,
            ack_state_machine=evaluate_ack_state_machine(session_state_result.entries),
        )

    mismatch = _operation_mismatch(instance, operation)
    op_content_mismatch = _operation_content_type_mismatch(instance)
    # On mismatch, rules follow the payload's own operation so they stay self-consistent.
    rules_operation = None if (mismatch or op_content_mismatch) else operation

    schema_validator = validator if validator is not None else RequestValidator()
    schema_errors = _collect_schema_errors(schema_validator, instance)
    parsed_envelope = [] if op_content_mismatch else _collect_envelope_errors(instance)
    envelope_errors = [
        *mismatch,
        *op_content_mismatch,
        *(
            e
            for e in parsed_envelope
            if not _envelope_issue_redundant_with_schema(e, schema_errors)
        ),
    ]

    business_rules = evaluate_business_rules(
        instance,
        operation=rules_operation,
        reference_time_utc_ms=reference_time_utc_ms,
        serialized_bytes=serialized_bytes,
        prior_state=prior_state,
    )
    ack_issues = evaluate_ack_state_machine(
        session_state_result.entries,
        current_payload=instance,
    )

    return ValidationResult.from_issues(
        schema_errors=schema_errors,
        envelope_errors=envelope_errors,
        business_rules=business_rules,
        ack_state_machine=ack_issues,
        session_state_errors=session_state_errors,
    )


def _operation_mismatch(instance: dict[str, Any], operation: str | None) -> list[ValidationIssue]:
    if operation is None:
        return []
    payload_operation = instance.get("operation")
    if payload_operation == operation:
        return []
    return [
        ValidationIssue(
            path="$.operation",
            message=(
                f"operation parameter {operation!r} does not match "
                f"payload.operation {payload_operation!r}"
            ),
            rule_id="operation_mismatch",
        )
    ]


def _operation_content_type_mismatch(instance: dict[str, Any]) -> list[ValidationIssue]:
    """Same rule as ``Request.operation_matches_content`` — checked before ``model_validate``."""
    op_raw = instance.get("operation")
    content = instance.get("content")
    if not isinstance(op_raw, str) or not isinstance(content, dict):
        return []
    try:
        op_enum = Operation(op_raw)
    except ValueError:
        return []
    expected = OPERATION_TO_CONTENT_TYPE.get(op_enum)
    if expected is None:
        return []
    actual = content.get("type")
    if actual == expected:
        return []
    return [
        ValidationIssue(
            path="$.content.type",
            message=(f"operation {op_raw!r} requires content.type {expected!r}, got {actual!r}"),
            rule_id="envelope",
        )
    ]


def _normalize_payload(
    payload: object | str,
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            return {}, [
                ValidationIssue(
                    path="$",
                    message=f"Invalid JSON: {exc.msg}",
                    rule_id="json_parse",
                )
            ]
        payload = parsed

    if not isinstance(payload, dict):
        return {}, [
            ValidationIssue(
                path="$",
                message=f"Expected a JSON object, got {type(payload).__name__}",
                rule_id="json_type",
            )
        ]

    return payload, []


def _collect_schema_errors(
    validator: RequestValidator,
    instance: dict[str, Any],
) -> list[ValidationIssue]:
    return schema_issues(validator.iter_errors(instance))


def _collect_envelope_errors(instance: dict[str, Any]) -> list[ValidationIssue]:
    try:
        Request.model_validate(instance)
    except PydanticValidationError as exc:
        return envelope_issues(list(exc.errors()))
    except ValueError as exc:
        return [
            ValidationIssue(
                path="$",
                message=str(exc),
                rule_id="envelope",
            )
        ]
    return []


def _envelope_issue_redundant_with_schema(
    issue: ValidationIssue,
    schema_errors: list[ValidationIssue],
) -> bool:
    """Drop pydantic issues already covered by a schema issue on the same subtree."""
    if issue.rule_id != "envelope":
        return False
    for schema_issue in schema_errors:
        ancestor = schema_issue.path
        if ancestor in ("$", "$.content", "$.content.type"):
            continue
        if _wire_path_is_descendant(ancestor, issue.path):
            return True
    return False


def _wire_path_is_descendant(ancestor: str, path: str) -> bool:
    """True when ``path`` is ``ancestor`` or extends it (wire JSON pointer style)."""
    if path == ancestor:
        return True
    if ancestor == "$":
        return bool(path and path.startswith("$"))
    return path.startswith(ancestor + ".") or path.startswith(ancestor + "[")
