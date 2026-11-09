"""Custom Bet rules: inner selection and event caps, odds anti-multiplication."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mts_client_integration.models.business_rules import (
    BusinessRuleIssue,
)
from mts_client_integration.services.business_rules.inputs import TicketRuleInput
from mts_client_integration.services.ticket_tree import (
    CUSTOM_BET_TYPE,
    as_dict,
    as_list,
    as_str,
    to_decimal,
    walk_selections,
)

MAX_CUSTOM_BET_INNER = 10
MAX_CUSTOM_BET_EVENTS = 5
_ODDS_PRODUCT_TOLERANCE = Decimal("0.01")


def check_custom_bets(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    issues: list[BusinessRuleIssue] = []
    for bet_index, bet in enumerate(bets):
        if not isinstance(bet, dict):
            continue
        base = f"$.content.bets[{bet_index}].selections"
        for path, node in walk_selections(as_list(bet.get("selections")), base):
            if node.get("type") == CUSTOM_BET_TYPE:
                issues.extend(_check_custom_bet(path, node))
    return issues


def _check_custom_bet(path: str, node: dict[str, Any]) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    inner = [c for c in as_list(node.get("selections")) if isinstance(c, dict)]
    if len(inner) < 2:
        issues.append(
            BusinessRuleIssue(
                "custom_bet_min_inner_selections",
                "error",
                f"{path}.selections",
                f"Custom bet has {len(inner)} inner selections; at least 2 are required.",
                maps_to_code=-440,
            )
        )
    if len(inner) > MAX_CUSTOM_BET_INNER:
        issues.append(
            BusinessRuleIssue(
                "custom_bet_max_inner_selections_10",
                "warning",
                f"{path}.selections",
                f"Custom bet has {len(inner)} inner selections; the cap is {MAX_CUSTOM_BET_INNER}.",
            )
        )
    events = {
        eid
        for c in inner
        if c.get("type") == "uf" and (eid := as_str(c.get("eventId"))) is not None
    }
    if len(events) > MAX_CUSTOM_BET_EVENTS:
        issues.append(
            BusinessRuleIssue(
                "custom_bet_max_events_5",
                "warning",
                f"{path}.selections",
                f"Custom bet spans {len(events)} events; the cap is {MAX_CUSTOM_BET_EVENTS}.",
            )
        )
    issues.extend(_check_custom_bet_odds(path, node, inner))
    if "useHarmOdds" not in node:
        issues.append(
            BusinessRuleIssue(
                "use_harm_odds_explicit",
                "info",
                f"{path}.useHarmOdds",
                "useHarmOdds is omitted and defaults to false; send it explicitly "
                "if harmonization is intended.",
            )
        )
    return issues


def _check_custom_bet_odds(
    path: str,
    node: dict[str, Any],
    inner: list[dict[str, Any]],
) -> list[BusinessRuleIssue]:
    combined = _decimal_odds(node.get("odds"))
    if combined is None:
        return []
    product = Decimal(1)
    have_all = True
    for selection in inner:
        selection_odds = _decimal_odds(selection.get("odds"))
        if selection_odds is None:
            have_all = False
            break
        product *= selection_odds
    if not have_all:
        return []
    if abs(product - combined) <= _ODDS_PRODUCT_TOLERANCE:
        return [
            BusinessRuleIssue(
                "custom_bet_odds_not_product",
                "error",
                f"{path}.odds.value",
                (
                    f"Custom bet combined odds {combined} equal the product of inner odds "
                    f"({product}); custom bet odds must come from the calculation API, "
                    "not multiplication."
                ),
                maps_to_code=-440,
            )
        ]
    return []


def _decimal_odds(odds: Any) -> Decimal | None:
    odds_dict = as_dict(odds)
    if odds_dict is None or odds_dict.get("type") != "decimal":
        return None
    return to_decimal(odds_dict.get("value"))
