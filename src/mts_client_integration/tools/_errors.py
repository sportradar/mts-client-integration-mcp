"""MCP tool error mapping helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import cast

from fastmcp.exceptions import ToolError

from mts_client_integration.models.mcp_outputs import BuildTicketOutput
from mts_client_integration.models.templates import BuildResult, PresetUnavailableError
from mts_client_integration.services.simulator.server import MockServerError


def run_build(shape: str, build: Callable[[], BuildResult]) -> BuildTicketOutput:
    """Run a preset build and convert expected failures into actionable ``ToolError``s."""
    try:
        result = build()
    except PresetUnavailableError as exc:
        raise ToolError(exc.describe()) from exc
    except ValueError as exc:
        raise ToolError(
            f"{exc}. See mts://templates/{shape} for required fields and example."
        ) from exc
    return cast(BuildTicketOutput, result.to_response_dict())


@contextmanager
def mock_errors() -> Iterator[None]:
    """Convert simulator failures into ``ToolError`` so MCP clients see ``isError``."""
    try:
        yield
    except (MockServerError, ValueError) as exc:
        raise ToolError(str(exc)) from exc
