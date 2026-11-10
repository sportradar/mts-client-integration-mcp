"""Integration tests for the FastMCP tool layer."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError

from mts_client_integration.services.preset_catalog import available_preset_ids
from mts_client_integration.services.simulator.catalog import valid_scenario_ids
from mts_client_integration.tools.mcp_server import create_server
from tests.factories import (
    builder_selection,
    placement_params,
    placement_payload,
    single_ticket_envelope,
)

pytestmark = pytest.mark.anyio

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
    return placement_params(selections=[builder_selection("sr:match:10000001")])


@pytest.fixture
async def client() -> AsyncIterator[Client[Any]]:
    async with Client(FastMCPTransport(create_server())) as connected:
        yield connected


async def _call(client: Client[Any], tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(tool, arguments)
    assert result.structured_content is not None
    return result.structured_content


# --------------------------------------------------------------------------- #
# Tool registry
# --------------------------------------------------------------------------- #


async def test_mcp_tool_names_match_catalog(client: Client[Any]) -> None:
    names = {tool.name for tool in await client.list_tools()}
    assert names == EXPECTED_TOOL_NAMES


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_TOOL_NAMES))
async def test_mcp_tool_exposes_object_output_schema(client: Client[Any], tool_name: str) -> None:
    by_name = {tool.name: tool for tool in await client.list_tools()}
    schema = by_name[tool_name].output_schema
    assert schema is not None
    assert schema.get("type") == "object"


# --------------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------------- #


async def test_lookup_rejection_code_resolves_operation_variant(client: Client[Any]) -> None:
    result = await _call(
        client, "lookup_rejection_code", {"code": 101, "operation": "ticket-cashout"}
    )
    assert result["found"] is True
    assert result["code"] == -101
    assert result["ambiguous"] is False


async def test_validate_ticket_request_accepts_valid_ticket(client: Client[Any]) -> None:
    result = await _call(client, "validate_ticket_request", {"payload": single_ticket_envelope()})
    assert result["schema_ok"] is True
    assert result["envelope_ok"] is True
    assert result["business_rules_ok"] is True
    assert result["ack_state_machine_ok"] is True


async def test_validate_ticket_request_reports_operation_mismatch(client: Client[Any]) -> None:
    result = await _call(
        client,
        "validate_ticket_request",
        {"payload": single_ticket_envelope(), "operation": "ticket-cancel"},
    )
    assert result["envelope_ok"] is False
    assert [e["rule_id"] for e in result["envelope_errors"]] == ["operation_mismatch"]


async def test_build_placement_returns_valid_payload(client: Client[Any]) -> None:
    result = await _call(
        client, "build_placement", {"shape": "single_prematch", "params": _placement_params()}
    )
    assert result["payload"]["operation"] == "ticket-placement"


async def test_list_ticket_shapes_returns_available_presets(client: Client[Any]) -> None:
    result = await _call(client, "list_ticket_shapes", {})
    shapes = {shape["shape"] for shape in result["shapes"]}
    assert shapes == set(available_preset_ids())
    assert result["count"] == len(shapes)


async def test_list_mock_scenarios_matches_catalog(client: Client[Any]) -> None:
    result = await _call(client, "list_mock_scenarios", {})
    listed = {s["id"] for s in result["scenarios"]} | {b["id"] for b in result["bundles"]}
    assert listed == set(valid_scenario_ids())


async def test_mock_status_when_not_started(client: Client[Any]) -> None:
    result = await _call(client, "mock_status", {})
    assert result["running"] is False


async def test_mock_lifecycle_through_mcp(client: Client[Any]) -> None:
    started = await _call(client, "start_mock", {"ws_port": 0, "oauth_port": 0})
    assert started["ok"] is True

    status = await _call(client, "mock_status", {})
    assert status["running"] is True
    assert status["ws_url"] == started["ws_url"]

    sent = await _call(client, "send_to_mock", {"payload": placement_payload()})
    (exchange,) = sent["exchanges"]
    assert exchange["reply"]["content"]["status"] == "accepted"

    stopped = await _call(client, "stop_mock", {})
    assert [e["direction"] for e in stopped["wire_log"]] == ["outbound", "inbound"]
    assert (await _call(client, "mock_status", {}))["running"] is False


# --------------------------------------------------------------------------- #
# Errors surface as ToolError
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        pytest.param(
            "build_placement",
            {"shape": "not_a_real_shape", "params": _placement_params()},
            id="build-unknown-shape",
        ),
        pytest.param(
            "build_placement",
            {"shape": "single_prematch", "params": {**_placement_params(), "stake": "0"}},
            id="build-zero-stake",
        ),
        pytest.param(
            "send_to_mock",
            {"payload": {"operation": "ticket-placement"}},
            id="send-without-running-mock",
        ),
        pytest.param("inject", {"event": "connection_blocked"}, id="inject-without-running-mock"),
        pytest.param("stop_mock", {}, id="stop-without-running-mock"),
        pytest.param("start_mock", {"scenarios": ["not_a_scenario"]}, id="start-unknown-scenario"),
    ],
)
async def test_invalid_call_is_tool_error(
    client: Client[Any], tool: str, arguments: dict[str, Any]
) -> None:
    with pytest.raises(ToolError):
        await client.call_tool(tool, arguments)


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #


async def _read_text(client: Client[Any], uri: str) -> str:
    contents = await client.read_resource(uri)
    assert contents
    return contents[0].text if hasattr(contents[0], "text") else str(contents[0])


@pytest.mark.parametrize(
    "uri",
    [
        "mts://schemas/ticket3/request",
        "mts://schemas/ticket3/response",
        "mts://templates/builder-schema",
        "mts://templates/single_prematch",
        "mts://integration/envelope-context",
        "mts://simulator/scenarios",
    ],
)
async def test_json_resource_is_readable(client: Client[Any], uri: str) -> None:
    data = json.loads(await _read_text(client, uri))
    assert isinstance(data, dict)
    assert data


@pytest.mark.parametrize(
    "uri", ["mts://schemas/session-state", "mts://integration/envelope-context.md"]
)
async def test_markdown_resource_is_readable(client: Client[Any], uri: str) -> None:
    assert (await _read_text(client, uri)).strip()


async def test_unknown_template_resource_returns_not_found(client: Client[Any]) -> None:
    data = json.loads(await _read_text(client, "mts://templates/unknown_shape_xyz"))
    assert data.get("found") is False
