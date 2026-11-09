"""Custom selection-tree assembly for complex golden-ticket shapes."""

from __future__ import annotations

from typing import Any

from mts_client_integration.models.templates import PlacementBuildParams, SelectionParams
from mts_client_integration.services.feed_selections import build_feed_selection, require


def _feeds(selections: list[SelectionParams]) -> list[dict[str, Any]]:
    return [build_feed_selection(sel) for sel in selections]


def _ways_node(ways_selections: list[SelectionParams]) -> dict[str, Any]:
    return {"type": "ways", "selections": _feeds(ways_selections)}


def uses_composite_selections(params: PlacementBuildParams) -> bool:
    return params.ways_selections is not None


def build_composite_bet_selections(params: PlacementBuildParams) -> list[dict[str, Any]]:
    """Assemble bet-level selection trees that standard bet_type mode cannot express."""
    ways = params.ways_selections
    if ways is None:
        msg = "ways_selections is required for composite shapes"
        raise ValueError(msg)

    if params.outer_selections:
        bankers = _feeds(params.selections or [])
        system_node: dict[str, Any] = {
            "type": "system",
            "size": require(params.size, "size"),
            "selections": [*bankers, _ways_node(ways)],
        }
        return [system_node, *_feeds(params.outer_selections)]

    if params.bet_type == "system":
        system_selections = _feeds(params.selections or [])
        return [
            {
                "type": "system",
                "size": require(params.size, "size"),
                "selections": [*system_selections, _ways_node(ways)],
            }
        ]

    return [*_feeds(params.selections or []), _ways_node(ways)]
