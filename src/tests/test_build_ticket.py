"""Tests for the golden-ticket builder (MVP capability #3)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from mts_client_integration.models.templates import (
    BuildResult,
    CashoutBuildParams,
    ExtSettlementBuildParams,
    PlacementBuildParams,
    PresetUnavailableError,
)
from mts_client_integration.services.preset_catalog import (
    available_preset_ids,
    get_preset,
    list_shapes,
    resolve_buildable_preset,
)
from mts_client_integration.services.preset_docs import describe_shape
from mts_client_integration.services.template_builder import (
    build_cashout,
    build_ext_settlement,
    build_placement,
)
from mts_client_integration.services.ticket_presets import PRESETS
from mts_client_integration.services.validation import validate_request_payload


def _selection(event_id: str, odds: str = "1.32") -> dict[str, Any]:
    return {
        "event_id": event_id,
        "market_id": "1",
        "outcome_id": "2",
        "odds": odds,
        "product_id": "3",
    }


def _e2e_channel() -> dict[str, Any]:
    return {"type": "internet", "ip": "127.0.0.1", "lang": "en"}


def _placement_base(**overrides: Any) -> dict[str, Any]:
    base = {
        "operator_id": "9985",
        "limit_id": 1409,
        "channel": _e2e_channel(),
        "stake": "10",
        "currency": "EUR",
    }
    base.update(overrides)
    return base


def _assert_builds_clean(payload: dict[str, Any], *, operation: str) -> None:
    result = validate_request_payload(payload, operation=operation)
    assert result.schema_ok is True
    assert result.envelope_ok is True
    assert result.business_rules_ok is True


def _example_params_for(shape: str) -> dict[str, Any]:
    preset = get_preset(shape)
    if preset.example_params is not None:
        return dict(preset.example_params)
    return dict(preset.defaults)


def _build_for_shape(shape: str) -> BuildResult:
    preset = PRESETS[shape]
    raw = _example_params_for(shape)
    if preset.builder == "placement":
        return build_placement(shape, PlacementBuildParams.model_validate(raw))
    if preset.builder == "cashout":
        return build_cashout(shape, CashoutBuildParams.model_validate(raw))
    return build_ext_settlement(shape, ExtSettlementBuildParams.model_validate(raw))


def test_all_available_presets_are_registered() -> None:
    available = available_preset_ids()
    assert len(available) == 34
    assert all(PRESETS[name].status == "available" for name in available)


def test_list_shapes_available_only_returns_buildable_set() -> None:
    shapes = list_shapes(include_planned=False)
    ids = {preset.shape for preset in shapes}
    assert ids == set(available_preset_ids())


@pytest.mark.parametrize("shape", available_preset_ids())
def test_each_available_shape_builds_schema_valid_ticket(shape: str) -> None:
    result = _build_for_shape(shape)
    assert result.shape == shape
    validation = validate_request_payload(result.payload, operation=result.operation)
    assert validation.schema_ok is True
    assert validation.envelope_ok is True
    assert validation.business_rules_ok is True


def test_preset_defaults_hold_no_integration_or_selection_data() -> None:
    forbidden_keys = {
        "operator_id",
        "limit_id",
        "channel",
        "stake",
        "currency",
        "selections",
        "bets",
        "ref",
        "percentage",
    }
    offending = {
        shape: sorted(forbidden_keys & preset.defaults.keys())
        for shape, preset in PRESETS.items()
        if forbidden_keys & preset.defaults.keys()
    }
    assert offending == {}


def test_trixie_builds_system_nest() -> None:
    result = build_placement(
        "trixie",
        PlacementBuildParams.model_validate(
            _placement_base(
                selections=[
                    _selection("sr:match:a"),
                    _selection("sr:match:b"),
                    _selection("sr:match:c"),
                ]
            )
        ),
    )
    selections = result.payload["content"]["bets"][0]["selections"]
    assert selections[-1]["type"] == "system"
    assert selections[-1]["size"] == [2, 3]


def test_multiple_ways_appends_ways_nest() -> None:
    result = build_placement(
        "multiple_ways",
        PlacementBuildParams.model_validate(_example_params_for("multiple_ways")),
    )
    selections = result.payload["content"]["bets"][0]["selections"]
    assert selections[-1]["type"] == "ways"
    assert len(selections) > 2


def test_ways_system_bankers_matches_e2e_nesting() -> None:
    result = build_placement(
        "ways_system_bankers",
        PlacementBuildParams.model_validate(_example_params_for("ways_system_bankers")),
    )
    selections = result.payload["content"]["bets"][0]["selections"]
    assert selections[0]["type"] == "system"
    inner = selections[0]["selections"]
    assert inner[-1]["type"] == "ways"
    assert selections[1]["type"] == "uf"


def test_banker_system_places_banker_after_system() -> None:
    result = build_placement(
        "banker_system",
        PlacementBuildParams.model_validate(_example_params_for("banker_system")),
    )
    selections = result.payload["content"]["bets"][0]["selections"]
    assert selections[0]["type"] == "system"
    assert selections[1]["type"] == "uf"


_SHAPES_WITH_REQUIRED_PARAMS = sorted(
    shape for shape in available_preset_ids() if PRESETS[shape].required_params
)


@pytest.mark.parametrize("shape", _SHAPES_WITH_REQUIRED_PARAMS)
def test_own_selections_without_required_params_raise(shape: str) -> None:
    preset = PRESETS[shape]
    params_dict = {
        key: value
        for key, value in _example_params_for(shape).items()
        if key not in preset.required_params
    }
    params_dict.setdefault("selections", [_selection("sr:match:1"), _selection("sr:match:2")])

    with pytest.raises(ValueError, match=preset.required_params[0]):
        build_placement(shape, PlacementBuildParams.model_validate(params_dict))


def test_own_bets_multibet() -> None:
    own_bet = {
        "selections": [_selection("sr:match:1"), _selection("sr:match:2")],
        "bet_type": "accumulator",
        "stake": "10",
        "currency": "EUR",
    }
    result = build_placement(
        "multibet",
        PlacementBuildParams.model_validate(
            _placement_base(
                bets=[
                    own_bet,
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
            )
        ),
    )

    bets = result.payload["content"]["bets"]
    event_ids = {node["eventId"] for node in bets[0]["selections"][0]["selections"]}
    assert len(bets) == 2
    assert event_ids == {"sr:match:1", "sr:match:2"}


def test_stake_override_on_system_preset() -> None:
    ex = _example_params_for("trixie")
    ex["stake"] = "5"
    result = build_placement("trixie", PlacementBuildParams.model_validate(ex))
    system = result.payload["content"]["bets"][0]["selections"][-1]
    assert len(system["selections"]) == 3
    assert result.payload["content"]["bets"][0]["stake"][0]["amount"] == "5"


@pytest.mark.parametrize(
    ("indexes", "message"),
    [([3], "out of range"), ([-1], "out of range"), ([1, 1], "duplicates")],
)
def test_invalid_banker_indexes_raise(indexes: list[int], message: str) -> None:
    selections = [_selection(f"sr:match:{i}") for i in range(3)]
    with pytest.raises(ValueError, match=message):
        build_placement(
            "banker_system",
            PlacementBuildParams.model_validate(
                _placement_base(
                    selections=selections,
                    banker_selection_indexes=indexes,
                    size=[2],
                )
            ),
        )


def test_banker_indexes_on_non_system_bet_type_raise() -> None:
    selections = [_selection("sr:match:1"), _selection("sr:match:2")]
    with pytest.raises(ValueError, match="only supported for bet_type 'system'"):
        build_placement(
            "accumulator",
            PlacementBuildParams.model_validate(
                _placement_base(selections=selections, banker_selection_indexes=[0])
            ),
        )


_WAYS = [
    {**_selection("sr:match:777"), "market_id": "3", "outcome_id": "5"},
    _selection("sr:match:777", odds="2.08"),
]
_TWO_SELECTIONS = [_selection("sr:match:1"), _selection("sr:match:2")]


@pytest.mark.parametrize(
    ("shape", "params", "message"),
    [
        (
            "accumulator",
            {
                **_placement_base(),
                "selections": _TWO_SELECTIONS,
                "outer_selections": [_selection("sr:match:3")],
            },
            "outer_selections requires ways_selections",
        ),
        (
            "accumulator",
            {**_placement_base(), "selections": _TWO_SELECTIONS, "ways_selections": _WAYS},
            "ways_selections requires bet_type 'single' or 'system'",
        ),
        (
            "ways_system",
            {
                **_placement_base(),
                "selections": _TWO_SELECTIONS,
                "ways_selections": _WAYS,
                "banker_selection_indexes": [0],
                "size": [2],
            },
            "banker_selection_indexes is not supported together with ways_selections",
        ),
        (
            "multibet",
            {
                **_placement_base(stake="10"),
                "bets": [
                    {
                        "selections": _TWO_SELECTIONS[:1],
                        "bet_type": "single",
                        "stake": "10",
                        "currency": "EUR",
                    }
                ],
                "ways_selections": _WAYS,
            },
            "not supported together with bets",
        ),
        (
            "multiple_ways",
            {**_placement_base(), "selections": _TWO_SELECTIONS, "ways_selections": _WAYS[:1]},
            "at least two same-event selections",
        ),
    ],
)
def test_inconsistent_composite_params_raise(
    shape: str,
    params: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_placement(shape, PlacementBuildParams.model_validate(params))


def test_full_cashout_is_non_partial() -> None:
    result = build_cashout(
        "full_cashout", CashoutBuildParams.model_validate(_example_params_for("full_cashout"))
    )
    assert result.payload["content"]["details"]["type"] == "ticket"


def test_external_settlement_builds_bet_level_envelope() -> None:
    result = build_ext_settlement(
        "external_settlement",
        ExtSettlementBuildParams.model_validate(_example_params_for("external_settlement")),
    )
    assert result.operation == "ticket-ext-settlement"
    content = result.payload["content"]
    assert content["type"] == "ext-settlement"
    assert content["details"]["type"] == "bet"
    assert content["details"]["betId"] == "Ticket_3668_bet_0"
    assert content["details"]["payout"][0]["traceId"] == "Source_8963"
    _assert_builds_clean(result.payload, operation="ticket-ext-settlement")


def test_unknown_shape_raises_with_available_list() -> None:
    with pytest.raises(PresetUnavailableError) as exc_info:
        build_placement(
            "not_a_shape",
            PlacementBuildParams.model_validate(_example_params_for("single_prematch")),
        )
    err = exc_info.value
    assert "does not exist" in err.message
    assert len(err.available_presets) == len(available_preset_ids())


def test_resolve_buildable_preset_ok() -> None:
    preset = resolve_buildable_preset("single_prematch", builder="placement")
    assert preset.shape == "single_prematch"


def test_wrong_builder_tool_raises() -> None:
    with pytest.raises(PresetUnavailableError, match="uses builder"):
        build_placement(
            "full_cashout",
            PlacementBuildParams.model_validate(_example_params_for("single_prematch")),
        )


def test_build_placement_produces_expected_shape() -> None:
    raw = _example_params_for("single_prematch")
    raw["selections"] = [_selection("sr:match:99")]
    result = build_placement("single_prematch", PlacementBuildParams.model_validate(raw))
    assert result.shape == "single_prematch"
    assert result.payload["operation"] == "ticket-placement"


def test_placement_missing_operator_id_validation_error() -> None:
    bad = {k: v for k, v in _example_params_for("single_prematch").items() if k != "operator_id"}
    with pytest.raises(ValidationError):
        PlacementBuildParams.model_validate(bad)


def test_describe_shape_has_schema_and_tool() -> None:
    for shape in available_preset_ids():
        doc = describe_shape(shape)
        assert doc["tool"]
        assert "params_json_schema" in doc
        assert doc["example_params"]


def test_end_customer_omitted_from_payload() -> None:
    ex = _example_params_for("single_prematch")
    ex.pop("end_customer_id", None)
    result = build_placement("single_prematch", PlacementBuildParams.model_validate(ex))
    ctx = result.payload["content"]["context"]
    assert "endCustomer" not in ctx
