"""Dataclasses and schemas for ticket validation results."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mts_client_integration.models.business_rules import (
    AckIssue,
    BusinessRuleIssue,
    SessionStateError,
)


def format_path(segments: Iterable[str | int]) -> str:
    """Render path segments as ``$.content.bets[0].stake`` (list indexes in brackets)."""
    path = "$"
    for segment in segments:
        path += f"[{segment}]" if isinstance(segment, int) else f".{segment}"
    return path


@dataclass(frozen=True)
class ValidationIssue:
    """A single schema or envelope validation problem."""

    path: str
    message: str
    rule_id: str


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating a Ticket 3.0 request payload.

    Combines four layers: JSON Schema, typed envelope, business rules, and the
    ACK / nACK state machine derived from the optional session_state.
    """

    schema_ok: bool
    schema_errors: tuple[ValidationIssue, ...]
    envelope_ok: bool
    envelope_errors: tuple[ValidationIssue, ...]
    business_rules: tuple[BusinessRuleIssue, ...] = ()
    ack_state_machine: tuple[AckIssue, ...] = ()
    session_state_errors: tuple[SessionStateError, ...] = ()

    @property
    def business_rules_ok(self) -> bool:
        """True when no business rule produced an ``error``-severity issue."""
        return not any(issue.severity == "error" for issue in self.business_rules)

    @property
    def ack_state_machine_ok(self) -> bool:
        """True when no ACK state-machine check produced an ``error`` issue."""
        return not any(issue.severity == "error" for issue in self.ack_state_machine)

    @classmethod
    def from_issues(
        cls,
        *,
        schema_errors: list[ValidationIssue],
        envelope_errors: list[ValidationIssue],
        business_rules: list[BusinessRuleIssue] | None = None,
        ack_state_machine: list[AckIssue] | None = None,
        session_state_errors: list[SessionStateError] | None = None,
    ) -> ValidationResult:
        return cls(
            schema_ok=not schema_errors,
            schema_errors=tuple(schema_errors),
            envelope_ok=not envelope_errors,
            envelope_errors=tuple(envelope_errors),
            business_rules=tuple(business_rules or ()),
            ack_state_machine=tuple(ack_state_machine or ()),
            session_state_errors=tuple(session_state_errors or ()),
        )

    def to_response_dict(self) -> dict[str, object]:
        """Serialize for MCP tool output."""
        return {
            "schema_ok": self.schema_ok,
            "schema_errors": [_issue_to_dict(issue) for issue in self.schema_errors],
            "envelope_ok": self.envelope_ok,
            "envelope_errors": [_issue_to_dict(issue) for issue in self.envelope_errors],
            "business_rules_ok": self.business_rules_ok,
            "business_rules": [_business_issue_to_dict(issue) for issue in self.business_rules],
            "ack_state_machine_ok": self.ack_state_machine_ok,
            "ack_state_machine": [_ack_issue_to_dict(issue) for issue in self.ack_state_machine],
            "session_state_errors": [
                _session_state_error_to_dict(err) for err in self.session_state_errors
            ],
        }


def _issue_to_dict(issue: ValidationIssue) -> dict[str, str]:
    return {
        "path": issue.path,
        "message": issue.message,
        "rule_id": issue.rule_id,
    }


def _business_issue_to_dict(issue: BusinessRuleIssue) -> dict[str, object]:
    return {
        "rule_id": issue.rule_id,
        "severity": issue.severity,
        "path": issue.path,
        "message": issue.message,
        "maps_to_code": issue.maps_to_code,
    }


def _ack_issue_to_dict(issue: AckIssue) -> dict[str, object]:
    return {
        "rule_id": issue.rule_id,
        "severity": issue.severity,
        "message": issue.message,
        "correlation_id": issue.correlation_id,
        "ticket_id": issue.ticket_id,
    }


def _session_state_error_to_dict(error: SessionStateError) -> dict[str, object]:
    return {"index": error.index, "message": error.message}
