"""Cancellation rules: allowed codes and cancellation percentage."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mts_client_integration.models.business_rules import (
    CANCEL_CODES_ALLOWED,
    PARTIAL_CANCEL_CODES,
    BusinessRuleIssue,
    PriorState,
)
from mts_client_integration.services.ticket_tree import (
    as_dict,
    as_str,
    to_decimal,
)


def check_cancel(cancel: dict[str, Any], state: PriorState) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    details = as_dict(cancel.get("details"))
    if details is None:
        return issues
    code = details.get("code")
    detail_type = as_str(details.get("type"))
    is_partial = detail_type in {"ticket-partial", "bet-partial"}
    if isinstance(code, int) and not isinstance(code, bool):
        if code not in CANCEL_CODES_ALLOWED:
            issues.append(
                BusinessRuleIssue(
                    "cancel_code_allowed",
                    "warning",
                    "$.content.details.code",
                    f"Cancellation code {code} is outside the E2E set (101/103/104/105/301/302).",
                )
            )
        if is_partial and code not in PARTIAL_CANCEL_CODES:
            issues.append(
                BusinessRuleIssue(
                    "partial_cancel_codes_only_101_103",
                    "error",
                    "$.content.details.code",
                    f"Partial cancellation supports only codes "
                    f"{sorted(PARTIAL_CANCEL_CODES)}, got {code}.",
                    maps_to_code=-2024,
                )
            )
    issues.extend(_check_cancel_percentage(details, state))
    return issues


def _check_cancel_percentage(
    details: dict[str, Any],
    state: PriorState,
) -> list[BusinessRuleIssue]:
    percentage = to_decimal(details.get("percentage"))
    if percentage is None:
        return []
    issues: list[BusinessRuleIssue] = []
    if not (Decimal(0) < percentage < Decimal(1)):
        issues.append(
            BusinessRuleIssue(
                "cancel_percentage_range",
                "error",
                "$.content.details.percentage",
                f"Cancellation percentage {percentage} must be within (0, 1).",
                maps_to_code=-2019,
            )
        )
    prior = state.previous_cancel_percentages(as_str(details.get("ticketId")))
    if prior and percentage < max(prior):
        issues.append(
            BusinessRuleIssue(
                "cancel_percentage_monotonic",
                "error",
                "$.content.details.percentage",
                f"Cancellation percentage {percentage} is lower than a previous "
                f"value ({max(prior)}).",
                maps_to_code=-2020,
            )
        )
    return issues
