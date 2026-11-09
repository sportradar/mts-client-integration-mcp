"""Wire-format builders for single feed selections (Sportradar ``uf`` and ``external``)."""

from __future__ import annotations

from typing import Any

from mts_client_integration.models.templates import SelectionParams


def require[T](value: T | None, name: str) -> T:
    """Return ``value`` or raise ``ValueError`` naming the missing field.

    ``SelectionParams`` validators already guarantee these fields, so a failure here
    means a builder was fed a model that bypassed validation.
    """
    if value is None:
        msg = f"{name} is required but missing"
        raise ValueError(msg)
    return value


def build_uf_selection(selection: SelectionParams) -> dict[str, Any]:
    node: dict[str, Any] = {
        "type": "uf",
        "productId": require(selection.product_id, "product_id"),
        "eventId": require(selection.event_id, "event_id"),
        "marketId": require(selection.market_id, "market_id"),
        "outcomeId": require(selection.outcome_id, "outcome_id"),
        "odds": {"type": "decimal", "value": selection.odds},
    }
    if selection.specifiers is not None:
        node["specifiers"] = selection.specifiers
    return node


def build_external_selection(selection: SelectionParams) -> dict[str, Any]:
    return {
        "type": "external",
        "event": require(selection.event, "event"),
        "outcome": require(selection.outcome, "outcome"),
        "odds": {"type": "decimal", "value": selection.odds},
        "expSettleTime": require(selection.exp_settle_time, "exp_settle_time"),
    }


def build_feed_selection(selection: SelectionParams) -> dict[str, Any]:
    if selection.type == "external":
        return build_external_selection(selection)
    return build_uf_selection(selection)
