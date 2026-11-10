"""MCP tools for rejection code lookup."""

from __future__ import annotations

from typing import cast

from fastmcp import Context, FastMCP

from mts_client_integration.models.mcp_outputs import RejectionLookupOutput
from mts_client_integration.models.rejection import (
    RejectionLookupResult,
    TicketContext,
    resolve_operation,
)
from mts_client_integration.services.catalog import RejectionCatalog
from mts_client_integration.tools._context import app_context


def perform_rejection_lookup(
    catalog: RejectionCatalog,
    code: int,
    *,
    ticket_context: TicketContext | None = None,
    operation: str | None = None,
) -> RejectionLookupResult:
    """Look up the MTS rejection message for a validation or response code."""
    resolved_operation = resolve_operation(
        operation=operation,
        ticket_context=ticket_context,
    )
    return catalog.lookup(code, operation=resolved_operation)


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def lookup_rejection_code(
        code: int,
        ctx: Context,
        ticket_context: TicketContext | None = None,
        operation: str | None = None,
    ) -> RejectionLookupOutput:
        """Look up the MTS rejection message for a validation or response code.

        Use when an integrator received a numeric rejection code from MTS and
        needs the canonical message text. When the catalog entry includes them,
        also returns ``steps_to_reproduce`` and ``fix_suggestions``.

        When the same code means different things for different request types,
        pass context from the rejected request so the correct message is returned.

        **How to fill ``ticket_context``**

        1. Find the Ticket 3.0 request JSON that MTS rejected (your outbound
           message, not the response).
        2. Copy its top-level ``operation`` value into ``ticket_context``.
        3. Call with e.g. ``ticket_context={"operation": "ticket-placement"}`` for
           a placement rejection, or ``ticket_context={"operation": "cashout-build"}``
           when disambiguating codes shared across operation families.

        Do not send the full request envelope unless that is all you have — only
        ``operation`` is read today. Additional ``ticket_context`` fields may be
        added later for root-cause hints.

        **Shortcut:** pass the same value as ``operation="ticket-placement"`` (or
        another operation string) when you do not need a structured context object.

        If neither ``ticket_context.operation`` nor ``operation`` is provided and
        the code has multiple meanings, the result includes all variants with
        ``ambiguous: true``; retry with the operation from your request.
        """
        result = perform_rejection_lookup(
            app_context(ctx).catalog,
            code,
            operation=operation,
            ticket_context=ticket_context,
        )
        return cast(RejectionLookupOutput, result.to_response_dict())
