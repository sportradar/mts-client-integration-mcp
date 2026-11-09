"""Golden-ticket preset registry queries."""

from __future__ import annotations

from mts_client_integration.models.templates import (
    BuilderKind,
    PresetUnavailableError,
    ShapePreset,
)
from mts_client_integration.services.ticket_presets import PRESETS


def available_preset_ids() -> list[str]:
    return sorted(preset.shape for preset in PRESETS.values() if preset.status == "available")


def preset_ids_for_builder(builder: BuilderKind) -> list[str]:
    return sorted(
        preset.shape
        for preset in PRESETS.values()
        if preset.status == "available" and preset.builder == builder
    )


def list_shapes(*, include_planned: bool = True) -> list[ShapePreset]:
    if include_planned:
        return list(PRESETS.values())
    return [preset for preset in PRESETS.values() if preset.status == "available"]


def get_preset(shape: str) -> ShapePreset:
    preset = PRESETS.get(shape)
    if preset is None:
        msg = f"unknown shape {shape!r}; known shapes: {', '.join(sorted(PRESETS))}"
        raise KeyError(msg)
    return preset


def unbuildable_preset_error(
    shape: str, *, builder: BuilderKind | None = None
) -> PresetUnavailableError | None:
    """Return the error for a missing or non-available preset, or ``None`` if it is buildable."""
    available = tuple(
        available_preset_ids() if builder is None else preset_ids_for_builder(builder)
    )
    preset = PRESETS.get(shape)
    if preset is None:
        message = f"Preset {shape!r} does not exist."
    elif preset.status != "available":
        message = f"Preset {shape!r} is not available (status={preset.status})."
    else:
        return None
    return PresetUnavailableError(shape=shape, message=message, available_presets=available)


def resolve_buildable_preset(shape: str, *, builder: BuilderKind) -> ShapePreset:
    """Return a preset for the given builder, or raise with guidance."""
    error = unbuildable_preset_error(shape)
    if error is not None:
        raise error
    preset = get_preset(shape)
    if preset.builder != builder:
        raise PresetUnavailableError(
            shape=shape,
            message=(
                f"Preset {shape!r} uses builder {preset.builder!r}, not {builder!r}. "
                "Use the tool for that builder."
            ),
            available_presets=tuple(preset_ids_for_builder(builder)),
        )
    return preset


def preset_unavailable_response(
    shape: str, *, builder: BuilderKind | None = None
) -> dict[str, object]:
    """Build an error response for a missing or non-buildable preset."""
    error = unbuildable_preset_error(shape, builder=builder)
    if error is None:
        msg = f"Preset {shape!r} is buildable; no unavailable response applies."
        raise ValueError(msg)
    return error.to_response_dict()
