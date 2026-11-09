"""MCP-facing rejection code lookup tool."""

from __future__ import annotations

from mts_client_integration.models.rejection import (
    RejectionLookupResult,
    TicketContext,
    resolve_operation,
)
from mts_client_integration.services.catalog import RejectionCatalog


def lookup_rejection_code(
    catalog: RejectionCatalog,
    code: int,
    *,
    ticket_context: TicketContext | None = None,
    operation: str | None = None,
) -> RejectionLookupResult:
    """Look up the MTS rejection message for a validation or response code.

    Use when an integrator received a numeric rejection code from MTS and
    needs the canonical message text. When the catalog entry includes them,
    also returns steps_to_reproduce and fix_suggestions.

    Pass ``ticket_context.operation`` copied from the rejected Ticket 3.0
    request envelope when the code is shared across operations. The standalone
    ``operation`` parameter is an equivalent shortcut.
    """
    resolved_operation = resolve_operation(
        operation=operation,
        ticket_context=ticket_context,
    )
    return catalog.lookup(code, operation=resolved_operation)
