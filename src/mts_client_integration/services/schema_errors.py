"""Reduce noisy JSON Schema ``oneOf``/``anyOf`` errors to the variant the caller meant."""

from __future__ import annotations

from collections import defaultdict

from jsonschema.exceptions import ValidationError

from mts_client_integration.models.validation import ValidationIssue, format_path

MAX_MESSAGE_CHARS = 300
VARIANT_MESSAGE = "Value does not match any of the allowed schema variants"
_UNION_KEYWORDS = frozenset({"oneOf", "anyOf"})
_DISCRIMINATOR = "type"


def schema_issues(errors: list[ValidationError]) -> list[ValidationIssue]:
    """Convert schema errors to issues: flatten unions, trim messages, drop duplicates."""
    issues = [
        ValidationIssue(
            path=format_path(leaf.absolute_path),
            message=_leaf_message(leaf),
            rule_id="jsonschema",
        )
        for error in errors
        for leaf in _flatten(error)
    ]
    return list(dict.fromkeys(issues))  # keeps order


def _flatten(error: ValidationError) -> list[ValidationError]:
    """Replace a union error by the errors of the variant the payload most likely targets.

    Variant choice: skip variants whose ``type`` discriminator did not match, then take
    the one with the fewest errors. If every variant failed the discriminator, the union
    error itself is returned (reported with a generic message).
    """
    if error.validator not in _UNION_KEYWORDS or not error.context:
        return [error]

    by_variant: dict[int, list[ValidationError]] = defaultdict(list)
    for sub_error in error.context:
        by_variant[int(sub_error.relative_schema_path[0])].append(sub_error)

    depth = len(error.absolute_path)
    candidates = [
        errors
        for errors in by_variant.values()
        if not any(_is_discriminator_mismatch(e, depth) for e in errors)
    ]
    if not candidates:
        return [error]
    best = min(candidates, key=len)
    return [leaf for sub_error in best for leaf in _flatten(sub_error)]


def _is_discriminator_mismatch(error: ValidationError, union_depth: int) -> bool:
    path = list(error.absolute_path)
    return (
        error.validator == "const" and len(path) == union_depth + 1 and path[-1] == _DISCRIMINATOR
    )


def _leaf_message(error: ValidationError) -> str:
    if error.validator in _UNION_KEYWORDS and error.context:
        return VARIANT_MESSAGE  # jsonschema's own text would echo the whole instance
    message = error.message
    if len(message) <= MAX_MESSAGE_CHARS:
        return message
    return message[: MAX_MESSAGE_CHARS - 3] + "..."
