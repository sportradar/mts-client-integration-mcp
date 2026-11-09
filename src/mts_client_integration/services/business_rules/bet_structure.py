"""Bet-structure rules: system, ways, accumulator, bankers, and bet ids."""

from __future__ import annotations

from typing import Any

from mts_client_integration.models.business_rules import (
    PREDEFINED_SYSTEM_SIZES,
    BusinessRuleIssue,
)
from mts_client_integration.services.business_rules.inputs import TicketRuleInput
from mts_client_integration.services.ticket_tree import (
    CUSTOM_BET_TYPE,
    NESTED_BET_TYPES,
    as_dict,
    as_list,
    as_str,
    child_selections,
    walk_selections,
)


def check_bet_ids_all_or_none(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    dict_bets = [b for b in bets if isinstance(b, dict)]
    if len(dict_bets) <= 1:
        return []
    with_id = [b for b in dict_bets if b.get("betId")]
    if 0 < len(with_id) < len(dict_bets):
        return [
            BusinessRuleIssue(
                "bet_ids_all_or_none",
                "error",
                "$.content.bets",
                "Inconsistent betId usage: either every bet must define betId or none.",
                maps_to_code=-212,
            )
        ]
    return []


def check_bet_types(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    issues: list[BusinessRuleIssue] = []
    for bet_index, bet in enumerate(bets):
        if not isinstance(bet, dict):
            continue
        base = f"$.content.bets[{bet_index}].selections"
        for path, node in walk_selections(as_list(bet.get("selections")), base):
            node_type = node.get("type")
            if node_type == "system":
                issues.extend(_check_system(path, node))
            elif node_type == "ways":
                issues.extend(_check_ways(path, node))
        issues.extend(_check_top_level_accumulator(bet, base))
    return issues


def _check_system(path: str, node: dict[str, Any]) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    selections = child_selections(node)
    selection_count = len(selections)
    sizes = [s for s in as_list(node.get("size")) if isinstance(s, int) and not isinstance(s, bool)]
    for size in sizes:
        if size < 1 or size > selection_count:
            issues.append(
                BusinessRuleIssue(
                    "system_size_valid",
                    "error",
                    f"{path}.size",
                    f"System size {size} is invalid for {selection_count} selections.",
                    maps_to_code=-207,
                )
            )
    if len(sizes) > 1:
        key = tuple(sorted(set(sizes)))
        name = PREDEFINED_SYSTEM_SIZES.get(key)
        if name is not None:
            issues.append(
                BusinessRuleIssue(
                    "predefined_system_sizes",
                    "info",
                    f"{path}.size",
                    f"System size {list(key)} matches predefined permutation '{name}'.",
                )
            )
        else:
            issues.append(
                BusinessRuleIssue(
                    "predefined_system_sizes",
                    "warning",
                    f"{path}.size",
                    f"System size {sorted(sizes)} does not match any known predefined permutation.",
                )
            )
    return issues


def _check_ways(path: str, node: dict[str, Any]) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    selections = child_selections(node)
    event_ids = {
        eid
        for selection in selections
        if selection.get("type") == "uf" and (eid := as_str(selection.get("eventId"))) is not None
    }
    if len(event_ids) > 1:
        issues.append(
            BusinessRuleIssue(
                "ways_same_event",
                "error",
                f"{path}.selections",
                f"Ways selection combines multiple events {sorted(event_ids)}; "
                "all selections of a ways node must share the same event.",
                maps_to_code=-333,
            )
        )
    if any(
        selection.get("type") in NESTED_BET_TYPES or selection.get("type") == CUSTOM_BET_TYPE
        for selection in selections
    ):
        issues.append(
            BusinessRuleIssue(
                "ways_nesting_order",
                "warning",
                f"{path}.selections",
                "Ways node should contain only feed selections; nested bet types are unexpected.",
                maps_to_code=-333,
            )
        )
    return issues


def _check_top_level_accumulator(bet: dict[str, Any], base: str) -> list[BusinessRuleIssue]:
    """Same-event / same-market checks for top-level accumulator selections.

    Only direct feed leaves that are NOT wrapped in a ``ways`` node are
    considered; same-event multiples must use ``ways``.
    """
    issues: list[BusinessRuleIssue] = []
    top = [s for s in as_list(bet.get("selections")) if isinstance(s, dict)]
    if any(s.get("type") == "system" for s in top):
        return issues  # system bankers/selections handled separately
    by_event: dict[str, list[str]] = {}
    by_event_market: set[tuple[str, str]] = set()
    for index, node in enumerate(top):
        if node.get("type") != "uf":
            continue
        event_id = as_str(node.get("eventId")) or ""
        market_id = as_str(node.get("marketId")) or ""
        path = f"{base}[{index}]"
        by_event.setdefault(event_id, []).append(path)
        key = (event_id, market_id)
        if key in by_event_market:
            issues.append(
                BusinessRuleIssue(
                    "accumulator_no_duplicate_market",
                    "error",
                    path,
                    f"Accumulator has duplicate event+market ({event_id}/{market_id}).",
                    maps_to_code=-321,
                )
            )
        by_event_market.add(key)
    for event_id, paths in by_event.items():
        if len(paths) > 1:
            issues.append(
                BusinessRuleIssue(
                    "accumulator_no_same_event_without_ways",
                    "error",
                    paths[-1],
                    f"Multiple accumulator selections on event {event_id} must be wrapped "
                    "in a 'ways' selection.",
                    maps_to_code=-322,
                )
            )
    return issues


def check_non_sr_and_bankers(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    issues: list[BusinessRuleIssue] = []
    for bet_index, bet in enumerate(bets):
        if not isinstance(bet, dict):
            continue
        base = f"$.content.bets[{bet_index}].selections"
        top = [s for s in as_list(bet.get("selections")) if isinstance(s, dict)]
        has_system = any(s.get("type") == "system" for s in top)
        for path, node in walk_selections(as_list(bet.get("selections")), base):
            if node.get("type") == "system" and _contains_external(node):
                issues.append(
                    BusinessRuleIssue(
                        "non_sr_in_system_forbidden",
                        "error",
                        path,
                        "System bet must not contain non-Sportradar (external) selections.",
                        maps_to_code=-214,
                    )
                )
        if has_system:
            for index, node in enumerate(top):
                if node.get("type") == "external":
                    issues.append(
                        BusinessRuleIssue(
                            "banker_on_non_sr_forbidden",
                            "error",
                            f"{base}[{index}]",
                            "Banker selection (top-level selection in a system bet) must "
                            "not be non-SR content.",
                            maps_to_code=-326,
                        )
                    )
    return issues


def _contains_external(node: dict[str, Any]) -> bool:
    for _, child in walk_selections(child_selections(node), "$"):
        if child.get("type") == "external":
            return True
    return False


def check_odds_change(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    bets = ctx.bets
    issues: list[BusinessRuleIssue] = []
    for bet_index, bet in enumerate(bets):
        if not isinstance(bet, dict):
            continue
        context = as_dict(bet.get("context"))
        if context is None:
            continue
        odds_change = context.get("oddsChange")
        if odds_change is not None and odds_change != "none":
            issues.append(
                BusinessRuleIssue(
                    "odds_change_default_none",
                    "warning",
                    f"$.content.bets[{bet_index}].context.oddsChange",
                    f"oddsChange is {odds_change!r}; if the alternative-odds feature is "
                    "disabled, only 'none' (or omitting the field) is accepted.",
                )
            )
    return issues
