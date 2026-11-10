"""FastMCP server for MTS client integration tools."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from mts_client_integration.models.ticket3.validator import (
    load_request_schema,
    load_response_schema,
)
from mts_client_integration.services import preset_catalog, preset_docs
from mts_client_integration.services.catalog import RejectionCatalog
from mts_client_integration.services.data_docs import session_state_documentation
from mts_client_integration.services.integration_context import (
    ENVELOPE_CONTEXT_DOC,
    get_envelope_context_documentation,
)
from mts_client_integration.services.simulator.server import MockServerError, MockServerManager
from mts_client_integration.tools import (
    build_ticket,
    lookup_rejection,
    mock_server,
    validate_ticket,
)
from mts_client_integration.tools._context import AppContext

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    app_context = AppContext(catalog=RejectionCatalog.load(), mock_manager=MockServerManager())
    try:
        yield app_context
    finally:
        if app_context.mock_manager.is_running:
            try:
                app_context.mock_manager.stop()
            except MockServerError:
                logger.exception("Failed to stop mock server during shutdown")


def create_server() -> FastMCP:
    mcp = FastMCP("MTS Client Integration", lifespan=lifespan)

    lookup_rejection.register(mcp)
    build_ticket.register(mcp)
    validate_ticket.register(mcp)
    mock_server.register(mcp)

    @mcp.resource("mts://schemas/session-state")
    def session_state_schema() -> str:
        """Describe the ``session_state`` input shape for ``validate_ticket_request``."""
        return session_state_documentation()

    @mcp.resource("mts://schemas/ticket3/request")
    def ticket3_request_schema() -> dict[str, object]:
        """External Ticket 3.0 request JSON Schema (outbound client → MTS envelopes)."""
        return load_request_schema()

    @mcp.resource("mts://schemas/ticket3/response")
    def ticket3_response_schema() -> dict[str, object]:
        """External Ticket 3.0 reply/response JSON Schema (inbound MTS → client envelopes)."""
        return load_response_schema()

    @mcp.resource("mts://templates/builder-schema")
    def ticket_builder_schema() -> dict[str, object]:
        """JSON Schemas for placement, cashout, and ext-settlement build params."""
        return preset_docs.get_builder_schema_documentation()

    @mcp.resource("mts://templates/{shape}")
    def ticket_template_preset(shape: str) -> dict[str, object]:
        """Preset metadata and example params for a named bet shape."""
        try:
            preset = preset_catalog.get_preset(shape)
        except KeyError:
            return preset_catalog.preset_unavailable_response(shape)
        if preset.status != "available":
            return preset_catalog.preset_unavailable_response(shape)
        return {"found": True, **preset_docs.describe_shape(shape)}

    @mcp.resource("mts://integration/envelope-context")
    def envelope_context() -> dict[str, object]:
        """Production-readiness contract for operatorId, limitId, and channel."""
        return get_envelope_context_documentation()

    @mcp.resource("mts://integration/envelope-context.md")
    def envelope_context_markdown() -> str:
        """Markdown guide for integrator envelope fields and builder workflow."""
        return ENVELOPE_CONTEXT_DOC

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
