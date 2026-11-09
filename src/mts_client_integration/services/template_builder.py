"""Build Ticket 3.0 request envelopes from a preset plus typed caller params."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from mts_client_integration.models.templates import (
    BuildResult,
    CashoutBuildParams,
    ExtSettlementBuildParams,
    PlacementBuildParams,
    ShapePreset,
)
from mts_client_integration.services.preset_catalog import resolve_buildable_preset
from mts_client_integration.services.ticket_builders import (
    build_cashout_envelope,
    build_ext_settlement_envelope,
    build_placement_envelope,
)


def _merge_params(preset: ShapePreset, params: BaseModel) -> dict[str, Any]:
    """Overlay explicitly set caller params on preset defaults.

    ``exclude_unset`` keeps values the caller set explicitly, even when they equal
    the model default, so presets never override them.
    """
    return {**preset.defaults, **params.model_dump(mode="python", exclude_unset=True)}


def _validate_params[ParamsT: BaseModel](
    shape: str, model: type[ParamsT], merged: dict[str, Any]
) -> ParamsT:
    try:
        return model.model_validate(merged)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
            for error in exc.errors()
        )
        msg = f"invalid params for shape {shape!r}: {problems}"
        raise ValueError(msg) from exc


def _require_preset_shape_params(preset: ShapePreset, merged: dict[str, Any]) -> None:
    missing = [key for key in preset.required_params if not merged.get(key)]
    if missing:
        msg = (
            f"shape {preset.shape!r} requires {', '.join(missing)}; "
            f"see mts://templates/{preset.shape} for a full example"
        )
        raise ValueError(msg)


def _validate_min_selections(preset: ShapePreset, params: PlacementBuildParams) -> None:
    if preset.min_selections is None:
        return
    if params.bets is not None:
        for index, bet in enumerate(params.bets):
            if len(bet.selections) < preset.min_selections:
                msg = (
                    f"shape {preset.shape!r} requires at least {preset.min_selections} "
                    f"selections in bets[{index}]"
                )
                raise ValueError(msg)
        return
    if params.ways_selections is not None:
        selection_count = len(params.selections or []) + len(params.ways_selections)
        if params.outer_selections:
            selection_count += len(params.outer_selections)
        if selection_count < preset.min_selections:
            msg = (
                f"shape {preset.shape!r} requires at least {preset.min_selections} "
                "selections including ways_selections"
            )
            raise ValueError(msg)
        return
    if params.selections is None or len(params.selections) < preset.min_selections:
        msg = f"shape {preset.shape!r} requires at least {preset.min_selections} selections"
        raise ValueError(msg)


def build_placement(shape: str, params: PlacementBuildParams) -> BuildResult:
    preset = resolve_buildable_preset(shape, builder="placement")
    merged = _merge_params(preset, params)
    _require_preset_shape_params(preset, merged)
    placement = _validate_params(shape, PlacementBuildParams, merged)
    _validate_min_selections(preset, placement)
    return BuildResult(
        shape=shape, operation="ticket-placement", payload=build_placement_envelope(placement)
    )


def build_cashout(shape: str, params: CashoutBuildParams) -> BuildResult:
    preset = resolve_buildable_preset(shape, builder="cashout")
    cashout = _validate_params(shape, CashoutBuildParams, _merge_params(preset, params))
    return BuildResult(
        shape=shape, operation="ticket-cashout", payload=build_cashout_envelope(cashout)
    )


def build_ext_settlement(shape: str, params: ExtSettlementBuildParams) -> BuildResult:
    preset = resolve_buildable_preset(shape, builder="ext_settlement")
    ext = _validate_params(shape, ExtSettlementBuildParams, _merge_params(preset, params))
    return BuildResult(
        shape=shape, operation="ticket-ext-settlement", payload=build_ext_settlement_envelope(ext)
    )
