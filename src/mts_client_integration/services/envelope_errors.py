"""Reduce noisy Pydantic ``Request`` validation errors (union branches, internal paths)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from pydantic_core import ErrorDetails

from mts_client_integration.models.validation import ValidationIssue, format_path

_MAX_MESSAGE_CHARS = 300


def envelope_issues(raw_errors: list[ErrorDetails]) -> list[ValidationIssue]:
    """Pick the best union branch per selection (or path) and strip internal segments."""
    filtered = [e for e in raw_errors if not _is_false_branch_type_literal(e)]
    by_group: dict[tuple[str | int, ...], list[ErrorDetails]] = defaultdict(list)
    for error in filtered:
        wire = _wire_path_segments(tuple(error.get("loc", ())))
        by_group[_selection_group_key(wire)].append(error)

    issues: list[ValidationIssue] = []
    for group in by_group.values():
        best = _pick_best_union_branch(group)
        issues.extend(_error_to_issues(e) for e in best)
    return list(dict.fromkeys(issues))


def _error_to_issues(error: ErrorDetails) -> ValidationIssue:
    wire = _wire_path_segments(tuple(error.get("loc", ())))
    message = str(error.get("msg", "Validation error"))
    if len(message) > _MAX_MESSAGE_CHARS:
        message = message[: _MAX_MESSAGE_CHARS - 3] + "..."
    return ValidationIssue(
        path=format_path(wire),
        message=message,
        rule_id="envelope",
    )


def _wire_path_segments(loc: Sequence[str | int]) -> list[str | int]:
    """Map model location to wire JSON: drop ``RootModel`` / variant class segments."""
    parts = list(loc)
    if len(parts) >= 2 and parts[0] == "content" and parts[1] == "ticket":
        parts = ["content", *parts[2:]]
    return [seg for seg in parts if not _is_internal_model_segment(seg)]


def _is_internal_model_segment(segment: str | int) -> bool:
    """Hand-written DTO / RootModel wrapper names are PascalCase; wire keys are camelCase."""
    return isinstance(segment, str) and bool(segment) and segment[0].isupper()


def _selection_group_key(wire: list[str | int]) -> tuple[str | int, ...]:
    """Group errors for the same logical selection (or odds union under that selection)."""
    for i, seg in enumerate(wire):
        if seg == "selections" and i + 1 < len(wire) and isinstance(wire[i + 1], int):
            return tuple(wire[: i + 2])
    return tuple(wire)


def _branch_signature(error: ErrorDetails) -> tuple[str | int, ...]:
    """Signature of the chosen pydantic variant branch (PascalCase segments only)."""
    return tuple(
        seg
        for seg in error.get("loc", ())
        if isinstance(seg, str) and bool(seg) and seg[0].isupper()
    )


def _branch_cost(errors: list[ErrorDetails]) -> tuple[int, int]:
    """Prefer fewer issues; tie-break on shorter locations (more specific branches)."""
    return (len(errors), sum(len(e.get("loc", ())) for e in errors))


def _pick_best_union_branch(errors: list[ErrorDetails]) -> list[ErrorDetails]:
    if len(errors) <= 1:
        return errors
    by_sig: dict[tuple[str | int, ...], list[ErrorDetails]] = defaultdict(list)
    for error in errors:
        by_sig[_branch_signature(error)].append(error)
    return min(by_sig.values(), key=_branch_cost)


def _is_false_branch_type_literal(error: ErrorDetails) -> bool:
    """Drop ``Input should be 'external'`` noise when another branch matches ``selection.type``."""
    if error.get("type") != "literal_error":
        return False
    loc = error.get("loc", ())
    if len(loc) < 4 or loc[-1] != "type":
        return False
    if loc[0] != "content":
        return False
    # Envelope ``content.type`` (ticket vs cancel) must stay visible.
    if len(loc) == 2 and loc[1] == "type":
        return False
    return any(isinstance(s, str) and s and s[0].isupper() for s in loc[2:-1])
