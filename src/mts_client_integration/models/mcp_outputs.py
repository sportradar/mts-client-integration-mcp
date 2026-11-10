"""Structured MCP tool output shapes (for outputSchema generation)."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class RejectionLookupOutput(TypedDict):
    code: int
    message: str | None
    found: bool
    operations: list[str]
    category: str | None
    ambiguous: bool
    steps_to_reproduce: NotRequired[list[str]]
    fix_suggestions: NotRequired[list[str]]


class BuildTicketOutput(TypedDict):
    shape: str
    operation: str
    payload: dict[str, Any]


class ListTicketShapesOutput(TypedDict):
    shapes: list[dict[str, Any]]
    count: int


class ValidationIssueDict(TypedDict, total=False):
    path: str
    message: str
    rule_id: str
    severity: str


class ValidationOutput(TypedDict):
    schema_ok: bool
    schema_errors: list[ValidationIssueDict]
    envelope_ok: bool
    envelope_errors: list[ValidationIssueDict]
    business_rules_ok: bool
    business_rules: list[ValidationIssueDict]
    ack_state_machine_ok: bool
    ack_state_machine: list[ValidationIssueDict]
    session_state_errors: list[ValidationIssueDict]
