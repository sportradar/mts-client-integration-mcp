"""Selection-level rules: leaf selections (odds, producer, market, external) and duplicates."""

from __future__ import annotations

from typing import Any

from mts_client_integration.models.business_rules import (
    KNOWN_PRODUCER_IDS,
    MIN_DECIMAL_ODDS,
    UNSUPPORTED_MARKET_IDS,
    BusinessRuleIssue,
)
from mts_client_integration.services.business_rules.inputs import TicketRuleInput
from mts_client_integration.services.business_rules.stakes import check_bet_stakes
from mts_client_integration.services.ticket_tree import (
    as_dict,
    as_list,
    as_str,
    iter_leaf_selections,
    to_decimal,
)

MAX_SELECTIONS = 100


def check_selection_cap(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    total = 0
    for bet in bets:
        if isinstance(bet, dict):
            total += sum(1 for _ in iter_leaf_selections(as_list(bet.get("selections")), "$"))
    if total > MAX_SELECTIONS:
        return [
            BusinessRuleIssue(
                "max_selections_100",
                "error",
                "$.content.bets",
                f"Ticket has {total} leaf selections; MTS allows at most {MAX_SELECTIONS}.",
                maps_to_code=-313,
            )
        ]
    return []


def check_leaf_rules(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    issues: list[BusinessRuleIssue] = []
    for bet_index, bet in enumerate(bets):
        if not isinstance(bet, dict):
            continue
        base = f"$.content.bets[{bet_index}].selections"
        for path, node in iter_leaf_selections(as_list(bet.get("selections")), base):
            issues.extend(_check_leaf(path, node))
        issues.extend(check_bet_stakes(bet, bet_index))
    return issues


def _check_leaf(path: str, node: dict[str, Any]) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    issues.extend(_check_min_odds(path, node))
    if node.get("type") == "uf":
        issues.extend(_check_producer(path, node))
        issues.extend(_check_market_rules(path, node))
    elif node.get("type") == "external":
        issues.extend(_check_external_event(path, node))
    return issues


def _check_min_odds(path: str, node: dict[str, Any]) -> list[BusinessRuleIssue]:
    odds = as_dict(node.get("odds"))
    if odds is None or odds.get("type") != "decimal":
        return []
    value = to_decimal(odds.get("value"))
    if value is not None and value < MIN_DECIMAL_ODDS:
        return [
            BusinessRuleIssue(
                "min_odds_1_01",
                "error",
                f"{path}.odds.value",
                f"Decimal odds {value} are below the minimum allowed of {MIN_DECIMAL_ODDS}.",
                maps_to_code=-316,
            )
        ]
    return []


def _check_producer(path: str, node: dict[str, Any]) -> list[BusinessRuleIssue]:
    product_id = as_str(node.get("productId"))
    if product_id is not None and product_id not in KNOWN_PRODUCER_IDS:
        return [
            BusinessRuleIssue(
                "producer_id_values",
                "warning",
                f"{path}.productId",
                (
                    f"productId {product_id!r} is not a classic UOF/C-Odds producer "
                    f"({sorted(KNOWN_PRODUCER_IDS)}); confirm this is intended (e.g. OneFeed)."
                ),
            )
        ]
    return []


def _check_market_rules(path: str, node: dict[str, Any]) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    market_id = as_str(node.get("marketId"))
    specifiers = as_str(node.get("specifiers")) or ""
    if market_id in UNSUPPORTED_MARKET_IDS:
        issues.append(
            BusinessRuleIssue(
                "goal_scorer_markets_unsupported",
                "warning",
                f"{path}.marketId",
                f"Market {market_id} (variant goal scorer) is not supported by MTS.",
            )
        )
    if market_id in {"38", "39", "40"} and "type=prematch" not in specifiers:
        issues.append(
            BusinessRuleIssue(
                "variant_goal_scorer_prematch_specifier",
                "warning",
                f"{path}.specifiers",
                f"Goalscorer market {market_id} typically requires a 'type=prematch' specifier.",
            )
        )
    if "&" in specifiers:
        issues.append(
            BusinessRuleIssue(
                "specifier_separator",
                "info",
                f"{path}.specifiers",
                "Specifiers use '&' separator; standard UOF specifiers use '|' or 'I' "
                "(InnBets markets are the usual exception).",
            )
        )
    return issues


def _check_external_event(path: str, node: dict[str, Any]) -> list[BusinessRuleIssue]:
    event = as_str(node.get("event"))
    if event is not None and ":" not in event:
        return [
            BusinessRuleIssue(
                "external_event_id_prefix",
                "warning",
                f"{path}.event",
                f"External event id {event!r} lacks a provider prefix; MTS expects "
                "'ext:match:<id>' (or an InnHub 'bg:'/'od:' prefix).",
                maps_to_code=-105,
            )
        ]
    return []


def check_duplicate_selections(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    issues: list[BusinessRuleIssue] = []
    for bet_index, bet in enumerate(bets):
        if not isinstance(bet, dict):
            continue
        base = f"$.content.bets[{bet_index}].selections"
        seen: set[tuple[str, str, str, str]] = set()
        for path, node in iter_leaf_selections(as_list(bet.get("selections")), base):
            identity = _leaf_identity(node)
            if identity is None:
                continue
            if identity in seen:
                issues.append(
                    BusinessRuleIssue(
                        "duplicate_event_selection",
                        "error",
                        path,
                        "Bet contains two selections with the same event and selection identity.",
                        maps_to_code=-327,
                    )
                )
            seen.add(identity)
    return issues


def _leaf_identity(node: dict[str, Any]) -> tuple[str, str, str, str] | None:
    if node.get("type") == "uf":
        return (
            as_str(node.get("eventId")) or "",
            as_str(node.get("marketId")) or "",
            as_str(node.get("outcomeId")) or "",
            as_str(node.get("specifiers")) or "",
        )
    if node.get("type") == "external":
        return (as_str(node.get("event")) or "", "", as_str(node.get("outcome")) or "", "")
    return None
