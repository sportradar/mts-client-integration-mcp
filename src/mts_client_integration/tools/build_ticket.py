"""MCP-facing golden-ticket builder tools."""

from __future__ import annotations

from mts_client_integration.models.templates import (
    BuildResult,
    CashoutBuildParams,
    ExtSettlementBuildParams,
    PlacementBuildParams,
)
from mts_client_integration.services.template_builder import (
    build_cashout as _build_cashout,
)
from mts_client_integration.services.template_builder import (
    build_ext_settlement as _build_ext_settlement,
)
from mts_client_integration.services.template_builder import (
    build_placement as _build_placement,
)


def build_placement(shape: str, params: PlacementBuildParams) -> BuildResult:
    """Build a ``ticket-placement`` envelope from a named preset and typed params."""
    return _build_placement(shape, params)


def build_cashout(shape: str, params: CashoutBuildParams) -> BuildResult:
    """Build a ``ticket-cashout`` envelope from a named preset and typed params."""
    return _build_cashout(shape, params)


def build_ext_settlement(shape: str, params: ExtSettlementBuildParams) -> BuildResult:
    """Build a ``ticket-ext-settlement`` envelope from a named preset and typed params."""
    return _build_ext_settlement(shape, params)
