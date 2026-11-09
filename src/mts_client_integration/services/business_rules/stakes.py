"""Stake rules: amounts, currency format, and multibet stake variety."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from mts_client_integration.models.business_rules import (
    BusinessRuleIssue,
)
from mts_client_integration.services.business_rules.inputs import TicketRuleInput
from mts_client_integration.services.ticket_tree import (
    as_list,
    as_str,
    to_decimal,
)

_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


def check_bet_stakes(bet: dict[str, Any], bet_index: int) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    for stake_index, stake in enumerate(as_list(bet.get("stake"))):
        if not isinstance(stake, dict):
            continue
        path = f"$.content.bets[{bet_index}].stake[{stake_index}]"
        amount = to_decimal(stake.get("amount"))
        stake_type = stake.get("type")
        if stake_type == "bonus":
            if amount is not None and amount < 0:
                issues.append(
                    BusinessRuleIssue(
                        "non_negative_bonus",
                        "error",
                        f"{path}.amount",
                        f"Bonus stake amount {amount} must not be negative.",
                        maps_to_code=-336,
                    )
                )
        elif amount is not None and amount <= 0:
            issues.append(
                BusinessRuleIssue(
                    "positive_stake",
                    "error",
                    f"{path}.amount",
                    f"Stake amount {amount} must be positive.",
                    maps_to_code=-301,
                )
            )
        issues.extend(_check_currency(stake.get("currency"), f"{path}.currency"))
    return issues


def _check_currency(currency: Any, path: str) -> list[BusinessRuleIssue]:
    if currency is None:
        return []
    text = as_str(currency)
    if text is None:
        return []
    if text == "mBTC":
        return []
    if not _CURRENCY_RE.match(text):
        return [
            BusinessRuleIssue(
                "currency_format",
                "error",
                path,
                f"Currency {text!r} is not a 3-letter ISO 4217 code (or 'mBTC').",
                maps_to_code=-307,
            )
        ]
    return []


def check_multibet(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    dict_bets = [b for b in bets if isinstance(b, dict)]
    if len(dict_bets) <= 1:
        return []
    amounts: set[Decimal] = set()
    for bet in dict_bets:
        for stake in as_list(bet.get("stake")):
            if isinstance(stake, dict) and (amount := to_decimal(stake.get("amount"))) is not None:
                amounts.add(amount)
    if len(amounts) > 1:
        return [
            BusinessRuleIssue(
                "multibet_distinct_stakes",
                "info",
                "$.content.bets",
                f"Ticket carries {len(dict_bets)} bets with differing stakes (multibet).",
            )
        ]
    return []
