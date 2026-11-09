"""Scenario catalog, bundles, and inject-event registry for the local simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ScenarioMode = Literal["passive", "reactive"]

LEAF_SCENARIOS: dict[str, dict[str, Any]] = {
    "frame_split": {
        "mode": "passive",
        "description": (
            "Reassemble multi-frame WS messages; close with code 1009 when a frame "
            "exceeds 32 KB, more than 4 frames, or total payload exceeds 128 KB."
        ),
    },
    "rate_limit": {
        "mode": "passive",
        "description": (
            "Token-bucket rate limiting (10 r/s integration, 500 r/s production). "
            "Excess requests receive a fixture rejection reply."
        ),
    },
    "token_2h_handover": {
        "mode": "passive",
        "description": (
            "Close WebSocket connections after connection_ttl_seconds (default 2h). "
            "Use inject(fast_forward_timer) to trigger immediately in local tests."
        ),
    },
    "spam_detector": {
        "mode": "passive",
        "description": (
            "Log each connect attempt timestamp and remote address for backoff / "
            "heartbeat analysis. Does not shape traffic."
        ),
    },
    "alt_stake_offer": {
        "mode": "reactive",
        "description": (
            "First ticket-placement is rejected with an alt-stake offer; resubmit "
            "with context.ref.type alt-stake is accepted."
        ),
    },
    "cancellation_matrix": {
        "mode": "reactive",
        "description": (
            "Each ticket-cancel receives a fixture reply for codes "
            "101/103/104/105/301/302; optional reject_code_103 param."
        ),
    },
    "partial_cashout_aggregator": {
        "mode": "reactive",
        "description": (
            "Tracks cumulative cashout percentage per ticketId; accepts 0.5 then "
            "0.8 pattern, rejects delta-percentage bug (0.3 after 0.5)."
        ),
    },
}

BUNDLES: dict[str, list[str]] = {
    "realistic_mix": ["frame_split", "rate_limit"],
    "connectivity_suite": ["token_2h_handover", "spam_detector"],
    "transaction_suite": [
        "alt_stake_offer",
        "cancellation_matrix",
        "partial_cashout_aggregator",
    ],
    "all": list(LEAF_SCENARIOS.keys()),
}

INJECT_EVENTS: dict[str, dict[str, Any]] = {
    "connection_blocked": {
        "description": "Drop connections and reject new handshakes.",
        "params": ["duration_seconds"],
    },
    "connection_unblocked": {
        "description": "Resume accepting WebSocket connections.",
        "params": [],
    },
    "force_disconnect": {
        "description": "Drop all connections once without blocking reconnect.",
        "params": [],
    },
    "fast_forward_timer": {
        "description": "Immediately fire token_2h_handover connection close.",
        "params": [],
    },
}

RATE_LIMIT_RPS: dict[str, int] = {
    "integration": 10,
    "production": 500,
}

DEFAULT_SCENARIOS = ["realistic_mix"]
DEFAULT_WS_PORT = 8765


@dataclass(frozen=True)
class ExpandedScenarios:
    requested: tuple[str, ...]
    active: frozenset[str]
    invalid: tuple[str, ...]


def expand_scenarios(requested: list[str] | None) -> ExpandedScenarios:
    """Resolve bundle IDs to leaf scenario IDs."""
    names = tuple(requested if requested else DEFAULT_SCENARIOS)
    active: set[str] = set()
    invalid: list[str] = []

    for name in names:
        if name in BUNDLES:
            active.update(BUNDLES[name])
        elif name in LEAF_SCENARIOS:
            active.add(name)
        else:
            invalid.append(name)

    return ExpandedScenarios(requested=names, active=frozenset(active), invalid=tuple(invalid))


def list_scenario_leaves() -> list[dict[str, Any]]:
    return [{"id": sid, **meta} for sid, meta in LEAF_SCENARIOS.items()]


def list_scenario_bundles() -> list[dict[str, Any]]:
    return [{"id": bid, "includes": includes} for bid, includes in BUNDLES.items()]


def list_inject_events() -> list[dict[str, Any]]:
    return [{"id": eid, **meta} for eid, meta in INJECT_EVENTS.items()]


def get_catalog_documentation() -> dict[str, Any]:
    return {
        "scenarios": list_scenario_leaves(),
        "bundles": list_scenario_bundles(),
        "inject_events": list_inject_events(),
        "rate_limit_profiles": RATE_LIMIT_RPS,
        "defaults": {
            "scenarios": DEFAULT_SCENARIOS,
            "ws_port": DEFAULT_WS_PORT,
            "connection_ttl_seconds": 7200,
        },
    }


def valid_scenario_ids() -> list[str]:
    return sorted(set(LEAF_SCENARIOS) | set(BUNDLES))
