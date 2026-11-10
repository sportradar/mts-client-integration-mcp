"""Shared test data builders.

Two families of helpers:

- *builder params* (snake_case) feed ``build_placement`` / ``build_cashout`` and the MCP
  builder tools;
- *envelopes* (camelCase) are raw Ticket 3.0 wire messages for validation and the mock.
"""

from __future__ import annotations

from typing import Any

from mts_client_integration.models.templates import PlacementBuildParams
from mts_client_integration.services.preset_catalog import get_preset
from mts_client_integration.services.template_builder import build_placement

FIXED_TIMESTAMP_MS = 1678876155000


# --------------------------------------------------------------------------- #
# Builder params
# --------------------------------------------------------------------------- #


def example_params_for(shape: str) -> dict[str, Any]:
    """Return a fresh copy of a preset's example params (falling back to defaults)."""
    preset = get_preset(shape)
    if preset.example_params is not None:
        return dict(preset.example_params)
    return dict(preset.defaults)


def builder_selection(event_id: str, odds: str = "1.32") -> dict[str, Any]:
    return {
        "event_id": event_id,
        "market_id": "1",
        "outcome_id": "2",
        "odds": odds,
        "product_id": "3",
    }


def placement_params(**overrides: Any) -> dict[str, Any]:
    """Integration context for ``build_placement``; selections are left to the caller."""
    base: dict[str, Any] = {
        "operator_id": "9985",
        "limit_id": 1409,
        "channel": {"type": "internet", "ip": "127.0.0.1", "lang": "en"},
        "stake": "10",
        "currency": "EUR",
    }
    base.update(overrides)
    return base


def placement_payload() -> dict[str, Any]:
    """A schema-valid ``single_prematch`` placement envelope built by the real builder."""
    params = PlacementBuildParams.model_validate(example_params_for("single_prematch"))
    return build_placement("single_prematch", params).payload


# --------------------------------------------------------------------------- #
# Raw Ticket 3.0 envelopes
# --------------------------------------------------------------------------- #


def uf_selection(
    event: str, market: str = "1", outcome: str = "1", odds: str = "1.5"
) -> dict[str, Any]:
    return {
        "type": "uf",
        "productId": "3",
        "eventId": event,
        "marketId": market,
        "outcomeId": outcome,
        "odds": {"type": "decimal", "value": odds},
    }


def bet(
    selections: list[dict[str, Any]], amount: str = "10", currency: str = "EUR"
) -> dict[str, Any]:
    return {
        "selections": selections,
        "stake": [{"type": "cash", "currency": currency, "amount": amount}],
    }


def ticket_envelope(bets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "ticket",
            "ticketId": "T1",
            "bets": bets,
            "context": {
                "channel": {"type": "internet", "ip": "1.2.3.4", "lang": "en"},
                "endCustomer": {"id": "user1"},
                "limitId": 1,
            },
        },
        "correlationId": "corr-1",
        "timestampUtc": FIXED_TIMESTAMP_MS,
        "operation": "ticket-placement",
        "version": "3.0",
    }


def single_ticket_envelope() -> dict[str, Any]:
    """Smallest valid placement: one single bet on one UF selection."""
    return ticket_envelope([bet([uf_selection("sr:match:1")])])
