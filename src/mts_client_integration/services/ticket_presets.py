"""Golden-ticket shape preset registry (~30 E2E bet shapes)."""

from __future__ import annotations

from typing import Any

from mts_client_integration.models.business_rules import PREDEFINED_SYSTEM_SIZES
from mts_client_integration.models.templates import ShapePreset

_EXAMPLE_SELECTION: dict[str, Any] = {
    "event_id": "sr:match:15050881",
    "market_id": "1",
    "outcome_id": "2",
    "odds": "1.32",
    "product_id": "3",
}

_EXAMPLE_LIVE: dict[str, Any] = {**_EXAMPLE_SELECTION, "product_id": "1"}

_EXAMPLE_SELECTIONS: list[dict[str, Any]] = [
    {**_EXAMPLE_SELECTION, "event_id": "sr:match:15050881"},
    {**_EXAMPLE_SELECTION, "event_id": "sr:match:15050882", "odds": "1.45"},
    {**_EXAMPLE_SELECTION, "event_id": "sr:match:15050883", "odds": "1.60"},
]

_WAYS_PAIR: list[dict[str, Any]] = [
    {
        "event_id": "sr:match:15050890",
        "market_id": "3",
        "outcome_id": "5",
        "odds": "1.21",
        "product_id": "3",
    },
    {
        "event_id": "sr:match:15050890",
        "market_id": "1",
        "outcome_id": "2",
        "odds": "2.08",
        "product_id": "3",
    },
]

_EXTERNAL_SELECTION: dict[str, Any] = {
    "type": "external",
    "event": "ext:match:99",
    "outcome": "ext-pre:9985:s1",
    "odds": "2.0",
    "exp_settle_time": 1_746_000_000_000,
}

_OUTRIGHT_SELECTION: dict[str, Any] = {
    "event_id": "sr:season:48238",
    "market_id": "534",
    "outcome_id": "pre:outcometext:9529",
    "odds": "3.5",
    "product_id": "3",
    "specifiers": "variant=pre:markettext:23370",
}

_LIVE_PREMATCH_MIXED: list[dict[str, Any]] = [
    {
        "event_id": "sr:match:14938771",
        "market_id": "223",
        "outcome_id": "1715",
        "odds": "1.1",
        "product_id": "3",
        "specifiers": "hcp=1.5",
    },
    {
        "event_id": "sr:match:15163591",
        "market_id": "1",
        "outcome_id": "2",
        "odds": "1.48",
        "product_id": "1",
        "specifiers": "hcp=1:0",
    },
    {
        "event_id": "sr:season:55413",
        "market_id": "534",
        "outcome_id": "pre:outcometext:9919",
        "odds": "2.0",
        "product_id": "3",
        "specifiers": "variant=pre:markettext:60279",
    },
]

_CUSTOM_BET_SELECTIONS: list[dict[str, Any]] = [
    {**_EXAMPLE_SELECTION, "event_id": "sr:match:16000001", "market_id": "1"},
    {**_EXAMPLE_SELECTION, "event_id": "sr:match:16000001", "market_id": "18", "outcome_id": "12"},
]

# Explicit E2E-style integration envelope for copy-paste examples only.
# The builder never fills this.
_E2E_INTEGRATION: dict[str, Any] = {
    "operator_id": "9985",
    "limit_id": 1409,
    "channel": {
        "type": "internet",
        "lang": "en",
        "ip": "212.7.5.2",
    },
    "stake": "10",
    "currency": "EUR",
}


def _selections_n(n: int, *, prefix: str = "sr:match:15") -> list[dict[str, Any]]:
    return [
        {
            "event_id": f"{prefix}{idx:05d}",
            "market_id": "1",
            "outcome_id": "2",
            "odds": f"1.{30 + idx}",
            "product_id": "3",
        }
        for idx in range(n)
    ]


def _system_preset(
    shape: str,
    description: str,
    size: list[int],
    *,
    example_stake: dict[str, Any] | None = None,
) -> ShapePreset:
    min_selections = max(size)
    return ShapePreset(
        shape=shape,
        description=description,
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "system", "size": size},
        min_selections=min_selections,
        example_params={
            **_E2E_INTEGRATION,
            **(example_stake or {}),
            "selections": _selections_n(min_selections),
        },
    )


def _named_system_presets() -> dict[str, ShapePreset]:
    presets: dict[str, ShapePreset] = {}
    slug_map = {
        "Trixie": "trixie",
        "Yankee": "yankee",
        "Super Yankee / Canadian": "super_yankee",
        "Heinz": "heinz",
        "Super Heinz": "super_heinz",
        "Goliath": "goliath",
        "Patent": "patent",
        "Lucky 15": "lucky_15",
        "Lucky 31": "lucky_31",
        "Lucky 63": "lucky_63",
    }
    for size_tuple, name in PREDEFINED_SYSTEM_SIZES.items():
        slug = slug_map[name]
        presets[slug] = _system_preset(
            slug,
            f"Predefined system {name}: size {list(size_tuple)}.",
            list(size_tuple),
        )
    presets["canadian"] = ShapePreset(
        shape="canadian",
        description="Alias for Super Yankee / Canadian (size [2, 3, 4, 5]).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "system", "size": [2, 3, 4, 5]},
        min_selections=5,
        example_params={**_E2E_INTEGRATION, "selections": _selections_n(5)},
    )
    return presets


PRESETS: dict[str, ShapePreset] = {
    "single_prematch": ShapePreset(
        shape="single_prematch",
        description="Single prematch UOF selection (productId 3).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "single"},
        min_selections=1,
        example_params={**_E2E_INTEGRATION, "selections": [_EXAMPLE_SELECTION]},
    ),
    "single_live": ShapePreset(
        shape="single_live",
        description="Single live UOF selection (productId 1).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "single"},
        min_selections=1,
        example_params={**_E2E_INTEGRATION, "selections": [_EXAMPLE_LIVE]},
    ),
    "accumulator": ShapePreset(
        shape="accumulator",
        description="Multi-selection accumulator (explicit accumulator wrapper).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "accumulator"},
        min_selections=2,
        example_params={**_E2E_INTEGRATION, "selections": _EXAMPLE_SELECTIONS},
    ),
    "live_prematch_mixed": ShapePreset(
        shape="live_prematch_mixed",
        description="Accumulator with prematch, live, and season/outright-style selections.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "accumulator"},
        min_selections=2,
        example_params={**_E2E_INTEGRATION, "selections": _LIVE_PREMATCH_MIXED},
    ),
    "outright": ShapePreset(
        shape="outright",
        description="Season/outright UOF selection (variant market + pre:outcometext outcome).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "single"},
        min_selections=1,
        example_params={**_E2E_INTEGRATION, "selections": [_OUTRIGHT_SELECTION]},
    ),
    "system_kn": ShapePreset(
        shape="system_kn",
        description="Generic system bet; pass size (e.g. [2] for doubles).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "system", "size": [2]},
        min_selections=2,
        example_params={**_E2E_INTEGRATION, "selections": _selections_n(3), "size": [2]},
    ),
    "multisystem": ShapePreset(
        shape="multisystem",
        description="System bet with multiple size groups (e.g. [1, 2, 4]).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "system", "size": [1, 2, 4]},
        min_selections=4,
        example_params={
            **_E2E_INTEGRATION,
            "selections": _selections_n(4),
            "size": [1, 2, 4],
        },
    ),
    "ways_same_event": ShapePreset(
        shape="ways_same_event",
        description="Ways bet: two or more selections on the same event.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "ways"},
        min_selections=2,
        example_params={**_E2E_INTEGRATION, "selections": _WAYS_PAIR},
    ),
    "multiple_ways": ShapePreset(
        shape="multiple_ways",
        description="Multiple events with a trailing same-event ways nest.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "single"},
        min_selections=2,
        example_params={
            **_E2E_INTEGRATION,
            "selections": _selections_n(4, prefix="sr:match:20"),
            "ways_selections": _WAYS_PAIR,
        },
        required_params=("ways_selections",),
    ),
    "ways_system": ShapePreset(
        shape="ways_system",
        description="System bet containing a same-event ways nest.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "system", "size": [2]},
        min_selections=3,
        example_params={
            **_E2E_INTEGRATION,
            "selections": _selections_n(2, prefix="sr:match:30"),
            "ways_selections": _WAYS_PAIR,
            "size": [2],
        },
        required_params=("ways_selections",),
    ),
    "ways_system_bankers": ShapePreset(
        shape="ways_system_bankers",
        description="System + ways + bankers nest (canonical shape).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "single", "size": [1]},
        min_selections=2,
        example_params={
            **_E2E_INTEGRATION,
            "selections": _selections_n(2, prefix="sr:match:45"),
            "ways_selections": _WAYS_PAIR,
            "outer_selections": [
                {
                    "event_id": "sr:match:47978191",
                    "market_id": "1",
                    "outcome_id": "2",
                    "odds": "2.3",
                    "product_id": "3",
                }
            ],
            "size": [1],
        },
        required_params=("ways_selections", "outer_selections"),
    ),
    "banker_system": ShapePreset(
        shape="banker_system",
        description="System bet with one or more banker selections outside the system nest.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "system", "size": [2]},
        min_selections=3,
        example_params={
            **_E2E_INTEGRATION,
            "selections": _selections_n(4),
            "banker_selection_indexes": [3],
            "size": [2],
        },
        required_params=("banker_selection_indexes",),
    ),
    "banker": ShapePreset(
        shape="banker",
        description="Alias for banker_system with a single banker selection.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "system", "size": [2]},
        min_selections=3,
        example_params={
            **_E2E_INTEGRATION,
            "selections": _selections_n(3),
            "banker_selection_indexes": [2],
            "size": [2],
        },
        required_params=("banker_selection_indexes",),
    ),
    "multibet": ShapePreset(
        shape="multibet",
        description="Ticket with multiple bets carrying distinct stakes.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={},
        min_selections=1,
        example_params={
            **_E2E_INTEGRATION,
            "bets": [
                {
                    "selections": [_EXAMPLE_SELECTION],
                    "bet_type": "single",
                    "stake": "10",
                    "currency": "EUR",
                },
                {
                    "selections": [
                        {
                            "event_id": "sr:match:47415409",
                            "market_id": "60",
                            "outcome_id": "3",
                            "odds": "2.4",
                            "product_id": "3",
                        }
                    ],
                    "bet_type": "single",
                    "stake": "20",
                    "currency": "EUR",
                },
            ],
        },
        required_params=("bets",),
    ),
    "custom_bet_single_event": ShapePreset(
        shape="custom_bet_single_event",
        description="Custom bet with inner selections on one event (distinct markets).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "custom_bet"},
        min_selections=2,
        example_params={
            **_E2E_INTEGRATION,
            "selections": _CUSTOM_BET_SELECTIONS,
            "custom_bet_odds": "2.5",
        },
        required_params=("custom_bet_odds",),
    ),
    "custom_bet_multi_event": ShapePreset(
        shape="custom_bet_multi_event",
        description="Custom bet spanning multiple events.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "custom_bet"},
        min_selections=2,
        example_params={
            **_E2E_INTEGRATION,
            "selections": [
                {**_EXAMPLE_SELECTION, "event_id": "sr:match:17000001"},
                {**_EXAMPLE_SELECTION, "event_id": "sr:match:17000002", "odds": "1.9"},
            ],
            "custom_bet_odds": "3.2",
        },
        required_params=("custom_bet_odds",),
    ),
    "alt_stake": ShapePreset(
        shape="alt_stake",
        description="Placement resubmit after alt-stake offer (context.ref.type alt-stake).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "single"},
        min_selections=1,
        example_params={
            **_E2E_INTEGRATION,
            "selections": [_EXAMPLE_SELECTION],
            "ref": {"type": "alt-stake", "ticket_id": "2337926700", "ticket_signature": "sigAlt"},
        },
        required_params=("ref",),
    ),
    "reoffer": ShapePreset(
        shape="reoffer",
        description="Placement resubmit after reoffer (context.ref.type reoffer).",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "single"},
        min_selections=1,
        example_params={
            **_E2E_INTEGRATION,
            "selections": [_EXAMPLE_SELECTION],
            "ref": {"type": "reoffer", "ticket_id": "2337926701", "ticket_signature": "sigRe"},
        },
        required_params=("ref",),
    ),
    "single_external": ShapePreset(
        shape="single_external",
        description="Single non-Sportradar (external) selection.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "single"},
        min_selections=1,
        example_params={**_E2E_INTEGRATION, "selections": [_EXTERNAL_SELECTION]},
    ),
    "mixed_sr_external": ShapePreset(
        shape="mixed_sr_external",
        description="Accumulator with UOF and external selections.",
        operation="ticket-placement",
        builder="placement",
        status="available",
        defaults={"bet_type": "accumulator"},
        min_selections=2,
        example_params={
            **_E2E_INTEGRATION,
            "selections": [_EXAMPLE_SELECTION, _EXTERNAL_SELECTION],
        },
    ),
    "partial_cashout_with_aggregator": ShapePreset(
        shape="partial_cashout_with_aggregator",
        description=(
            "Partial ticket cashout using cumulative percentage "
            "(e.g. 0.8 after an earlier 0.5 cashout)."
        ),
        operation="ticket-cashout",
        builder="cashout",
        status="available",
        defaults={"partial": True},
        example_params={
            "operator_id": "9985",
            "ticket_id": "2337926713",
            "ticket_signature": "sigAbc",
            "code": 0,
            "percentage": "0.8",
            "payout_amount": "8",
            "currency": "EUR",
        },
    ),
    "full_cashout": ShapePreset(
        shape="full_cashout",
        description="Full ticket cashout (non-partial).",
        operation="ticket-cashout",
        builder="cashout",
        status="available",
        defaults={"partial": False},
        example_params={
            "operator_id": "9985",
            "ticket_id": "2337926713",
            "ticket_signature": "sigAbc",
            "partial": False,
            "code": 0,
            "payout_amount": "18",
            "currency": "EUR",
        },
    ),
    "external_settlement": ShapePreset(
        shape="external_settlement",
        description=("External (non-SR) bet settlement after ticket acceptance."),
        operation="ticket-ext-settlement",
        builder="ext_settlement",
        status="available",
        defaults={"settlement_level": "bet"},
        example_params={
            "operator_id": "9985",
            "ticket_id": "Ticket_3668",
            "ticket_signature": "IEzuiEl82X+SmjWB3xDB0AIB6fUZVFOvmGKm6Rcvxm0=",
            "bet_id": "Ticket_3668_bet_0",
            "payout_amount": "11.45",
            "currency": "EUR",
            "trace_id": "Source_8963",
        },
    ),
    **_named_system_presets(),
}
