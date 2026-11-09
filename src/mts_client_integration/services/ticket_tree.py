"""Helpers for traversing raw Ticket 3.0 request payloads.

Business-rule checks operate on the raw JSON dict (not the typed envelope) so
they remain useful even when a payload fails strict schema validation. These
helpers centralise the tree-walking and content extraction logic.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Any

FEED_LEAF_TYPES: frozenset[str] = frozenset({"uf", "external"})
NESTED_BET_TYPES: frozenset[str] = frozenset({"accumulator", "system", "ways"})
DECORATOR_TYPES: frozenset[str] = frozenset({"odds-boost", "payout-modifier"})
CUSTOM_BET_TYPE = "uf-custom-bet"


def as_dict(value: Any) -> dict[str, Any] | None:
    """Return ``value`` if it is a dict, else ``None``."""
    return value if isinstance(value, dict) else None


def as_str(value: Any) -> str | None:
    """Return ``value`` if it is a str, else ``None``."""
    return value if isinstance(value, str) else None


def as_list(value: Any) -> list[Any]:
    """Return ``value`` if it is a list, else an empty list."""
    return value if isinstance(value, list) else []


def to_decimal(value: Any) -> Decimal | None:
    """Parse a numeric string/number into ``Decimal``; ``None`` on failure."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation, ValueError:
            return None
    return None


def child_selections(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the child selection nodes contained by a selection node."""
    node_type = node.get("type")
    if node_type in NESTED_BET_TYPES or node_type == CUSTOM_BET_TYPE:
        return [c for c in as_list(node.get("selections")) if isinstance(c, dict)]
    if node_type in DECORATOR_TYPES:
        inner = as_dict(node.get("selection"))
        return [inner] if inner is not None else []
    return []


def walk_selections(
    selections: list[Any],
    base_path: str,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(json_path, node)`` for every selection node, depth-first."""
    for index, node in enumerate(selections):
        if not isinstance(node, dict):
            continue
        path = f"{base_path}[{index}]"
        yield path, node
        children = child_selections(node)
        if children:
            child_base = _child_base_path(node, path)
            yield from walk_selections(children, child_base)


def _child_base_path(node: dict[str, Any], path: str) -> str:
    if node.get("type") in DECORATOR_TYPES:
        return f"{path}.selection"
    return f"{path}.selections"


def iter_leaf_selections(
    selections: list[Any],
    base_path: str,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(json_path, node)`` only for feed leaves (``uf``/``external``)."""
    for path, node in walk_selections(selections, base_path):
        if node.get("type") in FEED_LEAF_TYPES:
            yield path, node


def extract_ticket(content: dict[str, Any]) -> dict[str, Any] | None:
    """Return the ticket object for placement/inform/build content shapes."""
    content_type = content.get("type")
    if content_type == "ticket":
        return content
    if content_type in {"ticket-inform", "ticket-build"}:
        return as_dict(content.get("ticket"))
    return None


def extract_cashout(content: dict[str, Any]) -> dict[str, Any] | None:
    """Return the cashout object across cashout operation content shapes."""
    if content.get("type") == "cashout":
        return content
    nested = as_dict(content.get("cashout"))
    return nested


def extract_cancel(content: dict[str, Any]) -> dict[str, Any] | None:
    """Return the cancel object for ``cancel`` content."""
    if content.get("type") == "cancel":
        return content
    return None
