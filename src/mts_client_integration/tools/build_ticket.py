"""MCP tools for golden-ticket builders."""

from __future__ import annotations

from typing import Annotated, cast

from fastmcp import FastMCP
from pydantic import Field

from mts_client_integration.models.mcp_outputs import BuildTicketOutput, ListTicketShapesOutput
from mts_client_integration.models.templates import (
    CashoutBuildParams,
    ExtSettlementBuildParams,
    PlacementBuildParams,
)
from mts_client_integration.services import preset_catalog, preset_docs, template_builder
from mts_client_integration.tools._errors import run_build


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def build_placement(
        shape: Annotated[
            str,
            Field(
                description=(
                    "Placement preset id. Call list_ticket_shapes() or read "
                    "mts://templates/{shape} for the full contract and example."
                ),
                json_schema_extra={"enum": preset_catalog.preset_ids_for_builder("placement")},
            ),
        ],
        params: PlacementBuildParams,
    ) -> BuildTicketOutput:
        """Build a ``ticket-placement`` envelope from a named preset.

        **All business fields are required** in ``params`` (operator_id, limit_id,
        channel, stake, currency, selections or bets, etc.). The preset only fills
        shape facts such as ``bet_type`` and ``size``. Nothing is invented: never
        guess operator_id, limit_id, odds, or stake — ask the integrator.

        Read ``mts://templates/{shape}`` first for ``required_params``, JSON Schema,
        ``how_to_set_fields``, and a full copy-paste ``example_params``.

        Returns ``shape``, ``operation``, and ``payload``. Call ``validate_ticket_request``
        on ``payload`` for schema and business rules.
        """
        return run_build(shape, lambda: template_builder.build_placement(shape, params))

    @mcp.tool
    def build_cashout(
        shape: Annotated[
            str,
            Field(
                description=(
                    "Cashout preset id. Call list_ticket_shapes() or read mts://templates/{shape}."
                ),
                json_schema_extra={"enum": preset_catalog.preset_ids_for_builder("cashout")},
            ),
        ],
        params: CashoutBuildParams,
    ) -> BuildTicketOutput:
        """Build a ``ticket-cashout`` envelope from a named preset.

        Requires ``operator_id``, ``currency``, ``code`` (0..1000), ``ticket_id``,
        ``ticket_signature``, ``payout_amount``, and for partial cashouts the
        **cumulative** ``percentage`` in (0, 1). Do not invent these — ask the integrator.

        Read ``mts://templates/{shape}`` for the full example.
        """
        return run_build(shape, lambda: template_builder.build_cashout(shape, params))

    @mcp.tool
    def build_ext_settlement(
        shape: Annotated[
            str,
            Field(
                description=(
                    "External-settlement preset id. Call list_ticket_shapes() or read "
                    "mts://templates/{shape}."
                ),
                json_schema_extra={"enum": preset_catalog.preset_ids_for_builder("ext_settlement")},
            ),
        ],
        params: ExtSettlementBuildParams,
    ) -> BuildTicketOutput:
        """Build a ``ticket-ext-settlement`` envelope from a named preset.

        Requires ``operator_id``, ``currency``, ticket ids, signature, and payout.
        Bet-level settlement requires ``bet_id``. Read ``mts://templates/{shape}`` for the example.
        """
        return run_build(shape, lambda: template_builder.build_ext_settlement(shape, params))

    @mcp.tool
    def list_ticket_shapes(
        include_planned: bool = False,
    ) -> ListTicketShapesOutput:
        """List golden-ticket shape presets and their availability status.

        Use to discover valid ``shape`` values for ``build_placement``, ``build_cashout``,
        and ``build_ext_settlement``. Shapes with
        ``status: available`` can be built today; ``planned`` shapes are documented
        aliases awaiting E2E canonical JSON.
        """
        presets = preset_catalog.list_shapes(include_planned=include_planned)
        return cast(
            ListTicketShapesOutput,
            {
                "shapes": [preset_docs.preset_to_resource_dict(p) for p in presets],
                "count": len(presets),
            },
        )
