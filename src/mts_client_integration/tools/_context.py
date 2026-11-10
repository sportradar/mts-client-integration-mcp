"""Shared MCP server lifespan context."""

from __future__ import annotations

from dataclasses import dataclass

from fastmcp import Context
from fastmcp.exceptions import ToolError

from mts_client_integration.services.catalog import RejectionCatalog
from mts_client_integration.services.simulator.server import MockServerManager


@dataclass
class AppContext:
    catalog: RejectionCatalog
    mock_manager: MockServerManager


def app_context(ctx: Context) -> AppContext:
    request_context = ctx.request_context
    if request_context is None:
        raise ToolError("MCP request context is unavailable")
    app: AppContext = request_context.lifespan_context
    return app
