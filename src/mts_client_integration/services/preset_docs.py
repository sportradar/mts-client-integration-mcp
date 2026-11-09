"""Agent-facing documentation for golden-ticket presets and their build params."""

from __future__ import annotations

from mts_client_integration.models.templates import (
    BuilderKind,
    CashoutBuildParams,
    ExtSettlementBuildParams,
    PlacementBuildParams,
    ShapePreset,
)
from mts_client_integration.services.preset_catalog import get_preset

BuildParamsModel = type[PlacementBuildParams | CashoutBuildParams | ExtSettlementBuildParams]

_PARAMS_MODEL_BY_BUILDER: dict[BuilderKind, BuildParamsModel] = {
    "placement": PlacementBuildParams,
    "cashout": CashoutBuildParams,
    "ext_settlement": ExtSettlementBuildParams,
}

_TOOL_BY_BUILDER: dict[BuilderKind, str] = {
    "placement": "build_placement",
    "cashout": "build_cashout",
    "ext_settlement": "build_ext_settlement",
}

_FIELD_HOW_TO: dict[str, str] = {
    "operator_id": "From the integrator's MTS profile (never guess).",
    "limit_id": "Limit id configured for this operator in MTS (rejection -509 if wrong).",
    "channel": (
        "Depends on channel type per Ticket 3.0 schema: internet/mobile need ip+lang; "
        "retail needs shopId; terminal needs shopId+terminalId."
    ),
    "stake": "Positive decimal stake string from the integrator.",
    "payout_amount": "Positive decimal payout string from the integrator.",
    "currency": "ISO 4217 three-letter code or mBTC.",
    "percentage": "Cumulative fraction of original stake in (0, 1), not the delta.",
    "code": "Cashout code 0..1000 per schema; use operator docs for the correct value.",
}

_SELECTIONS_DISPLAY = "selections (see min_selections)"


def get_builder_schema_documentation() -> dict[str, object]:
    """JSON Schemas for the three typed build param models (for MCP resources)."""
    return {
        builder: model.model_json_schema() for builder, model in _PARAMS_MODEL_BY_BUILDER.items()
    }


def _required_param_names(preset: ShapePreset) -> list[str]:
    """Plain field names the caller must supply for ``preset`` (``selections`` included)."""
    if preset.builder == "cashout":
        names = [
            "operator_id",
            "ticket_id",
            "ticket_signature",
            "payout_amount",
            "currency",
            "code",
        ]
        if bool(preset.defaults.get("partial", True)):
            names.append("percentage")
        return names
    if preset.builder == "ext_settlement":
        names = ["operator_id", "ticket_id", "ticket_signature", "payout_amount", "currency"]
        if preset.defaults.get("settlement_level", "bet") == "bet":
            names.append("bet_id")
        return names
    names = ["operator_id", "limit_id", "channel", "stake", "currency"]
    if "bets" not in preset.required_params:
        names.append("selections")
    return [*names, *preset.required_params]


def _required_params_display(preset: ShapePreset) -> list[str]:
    return [
        _SELECTIONS_DISPLAY if name == "selections" else name
        for name in _required_param_names(preset)
    ]


def preset_to_resource_dict(preset: ShapePreset) -> dict[str, object]:
    return {
        "shape": preset.shape,
        "description": preset.description,
        "operation": preset.operation,
        "builder": preset.builder,
        "tool": _TOOL_BY_BUILDER[preset.builder],
        "status": preset.status,
        "fixed_defaults": preset.defaults,
        "min_selections": preset.min_selections,
        "required_params": _required_params_display(preset),
        "example_params": preset.example_params,
    }


def describe_shape(shape: str) -> dict[str, object]:
    """Rich preset description: tool, constraints, how-to, and full example."""
    preset = get_preset(shape)
    how_to_set = {
        name: _FIELD_HOW_TO[name] for name in _required_param_names(preset) if name in _FIELD_HOW_TO
    }
    return {
        **preset_to_resource_dict(preset),
        "how_to_set_fields": how_to_set,
        "params_json_schema": _PARAMS_MODEL_BY_BUILDER[preset.builder].model_json_schema(),
    }
