"""Integration tests for the FastMCP tool layer."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import pytest
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError

from mts_client_integration.tools.mcp_server import create_server

EXPECTED_TOOL_NAMES = frozenset(
    {
        "lookup_rejection_code",
        "build_placement",
        "build_cashout",
        "build_ext_settlement",
        "list_ticket_shapes",
        "validate_ticket_request",
        "list_mock_scenarios",
        "start_mock",
        "inject",
        "stop_mock",
        "mock_status",
        "send_to_mock",
    }
)


def _placement_params() -> dict[str, Any]:
    return {
        "operator_id": "9985",
        "limit_id": 1409,
        "channel": {"type": "internet", "ip": "127.0.0.1", "lang": "en"},
        "stake": "10",
        "currency": "EUR",
        "selections": [
            {
                "event_id": "sr:match:10000001",
                "market_id": "1",
                "outcome_id": "2",
                "odds": "1.32",
                "product_id": "3",
            }
        ],
    }


T = TypeVar("T")


async def _with_client(coro: Callable[[Client[Any]], Awaitable[T]]) -> T:
    server = create_server()
    async with Client(FastMCPTransport(server)) as client:
        return await coro(client)


def test_mcp_tool_names_match_catalog() -> None:
    async def run(client: Client[Any]) -> None:
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        assert names == EXPECTED_TOOL_NAMES

    asyncio.run(_with_client(run))


def test_mcp_tools_expose_output_schema() -> None:
    async def run(client: Client[Any]) -> None:
        tools = await client.list_tools()
        by_name = {tool.name: tool for tool in tools}
        for name in EXPECTED_TOOL_NAMES:
            schema = by_name[name].output_schema
            assert schema is not None, name
            assert schema.get("type") == "object"

    asyncio.run(_with_client(run))


def test_build_placement_unknown_shape_is_tool_error() -> None:
    async def run(client: Client[Any]) -> None:
        with pytest.raises(ToolError):
            await client.call_tool(
                "build_placement",
                {"shape": "not_a_real_shape", "params": _placement_params()},
            )

    asyncio.run(_with_client(run))


def test_build_placement_invalid_params_is_tool_error() -> None:
    async def run(client: Client[Any]) -> None:
        bad = _placement_params()
        bad["stake"] = "0"
        with pytest.raises(ToolError):
            await client.call_tool(
                "build_placement",
                {"shape": "single_prematch", "params": bad},
            )

    asyncio.run(_with_client(run))


def test_send_to_mock_without_server_is_tool_error() -> None:
    async def run(client: Client[Any]) -> None:
        with pytest.raises(ToolError):
            await client.call_tool("send_to_mock", {"payload": {"operation": "ticket-placement"}})

    asyncio.run(_with_client(run))


def test_inject_without_server_is_tool_error() -> None:
    async def run(client: Client[Any]) -> None:
        with pytest.raises(ToolError):
            await client.call_tool("inject", {"event": "connection_blocked"})

    asyncio.run(_with_client(run))


def test_unknown_template_resource_returns_not_found() -> None:
    async def run(client: Client[Any]) -> None:
        contents = await client.read_resource("mts://templates/unknown_shape_xyz")
        assert contents
        text = contents[0].text if hasattr(contents[0], "text") else str(contents[0])
        data = json.loads(text)
        assert data.get("found") is False

    asyncio.run(_with_client(run))
