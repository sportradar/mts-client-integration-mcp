"""Cash-out rules: payout, cumulative percentage, and currency match."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mts_client_integration.models.business_rules import (
    BusinessRuleIssue,
    PriorState,
)
from mts_client_integration.services.ticket_tree import (
    as_dict,
    as_list,
    as_str,
    to_decimal,
)


def check_cashout(cashout: dict[str, Any], state: PriorState) -> list[BusinessRuleIssue]:
    details = as_dict(cashout.get("details"))
    if details is None:
        return []
    issues: list[BusinessRuleIssue] = []
    issues.extend(_check_cashout_payout(details))
    issues.extend(_check_cashout_percentage(details, state))
    return issues


def _check_cashout_payout(details: dict[str, Any]) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    for index, payout in enumerate(as_list(details.get("payout"))):
        if not isinstance(payout, dict):
            continue
        amount = to_decimal(payout.get("amount"))
        if amount is not None and amount <= 0:
            issues.append(
                BusinessRuleIssue(
                    "cashout_payout_positive",
                    "error",
                    f"$.content.details.payout[{index}].amount",
                    f"Cash-out payout amount {amount} must be positive.",
                    maps_to_code=-203,
                )
            )
    return issues


def _check_cashout_percentage(
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
                "cashout_percentage_range",
                "error",
                "$.content.details.percentage",
                f"Cash-out percentage {percentage} must be within (0, 1).",
                maps_to_code=-210,
            )
        )
    ticket_id = as_str(details.get("ticketId"))
    prior = state.previous_cashout_percentages(ticket_id)
    if prior:
        issues.append(
            BusinessRuleIssue(
                "cashout_cumulative_percentage",
                "warning",
                "$.content.details.percentage",
                (
                    f"This is a follow-up partial cash-out on ticket {ticket_id!r}; "
                    f"'percentage' must be the cumulative fraction of the original stake "
                    f"(prior values: {[str(p) for p in prior]}), not the incremental amount."
                ),
                maps_to_code=-211,
            )
        )
        if percentage < max(prior):
            issues.append(
                BusinessRuleIssue(
                    "cashout_percentage_monotonic",
                    "error",
                    "$.content.details.percentage",
                    f"Cash-out percentage {percentage} is lower than a previous "
                    f"value ({max(prior)}).",
                    maps_to_code=-211,
                )
            )
    issues.extend(_check_cashout_currency(details, ticket_id, state))
    return issues


def _check_cashout_currency(
    details: dict[str, Any],
    ticket_id: str | None,
    state: PriorState,
) -> list[BusinessRuleIssue]:
    placement = state.currencies_placed_for(ticket_id)
    if not placement:
        return []
    issues: list[BusinessRuleIssue] = []
    for index, payout in enumerate(as_list(details.get("payout"))):
        if not isinstance(payout, dict):
            continue
        currency = as_str(payout.get("currency"))
        if currency is not None and currency not in placement:
            issues.append(
                BusinessRuleIssue(
                    "cashout_currency_matches_placement",
                    "error",
                    f"$.content.details.payout[{index}].currency",
                    f"Cash-out currency {currency!r} does not match the placement "
                    f"currency ({sorted(placement)}).",
                    maps_to_code=-307,
                )
            )
    return issues
