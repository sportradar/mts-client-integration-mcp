"""Tests for the targeted local MTS simulator (MVP capability #4)."""

from __future__ import annotations

import asyncio
import json
import socket
import time
from collections.abc import Generator
from typing import Any, cast, get_args

import pytest
import websockets

from mts_client_integration.models.templates import CashoutBuildParams, PlacementBuildParams
from mts_client_integration.services.preset_catalog import get_preset
from mts_client_integration.services.simulator.catalog import (
    INJECT_EVENTS,
    InjectEvent,
    expand_scenarios,
)
from mts_client_integration.services.simulator.server import MockServerError, MockServerManager
from mts_client_integration.services.template_builder import build_cashout, build_placement
from mts_client_integration.services.validation import validate_request_payload
from mts_client_integration.tools.mock_server import (
    inject_mock,
    send_to_mock,
    start_mock,
    stop_mock,
)


def _example_params_for(shape: str) -> dict[str, Any]:
    preset = get_preset(shape)
    if preset.example_params is not None:
        return dict(preset.example_params)
    return dict(preset.defaults)


def _placement_payload() -> dict[str, Any]:
    raw = _example_params_for("single_prematch")
    result = build_placement("single_prematch", PlacementBuildParams.model_validate(raw))
    return result.payload


@pytest.fixture
def mock_manager() -> Generator[MockServerManager]:
    manager = MockServerManager()
    yield manager
    if manager.is_running:
        manager.stop()


def _cancel_envelope(ticket_id: str, code: int) -> dict[str, Any]:
    return {
        "operatorId": "9985",
        "content": {
            "type": "cancel",
            "details": {
                "type": "ticket",
                "ticketId": ticket_id,
                "ticketSignature": "sig",
                "code": code,
            },
        },
        "correlationId": f"corr-cancel-{code}",
        "timestampUtc": int(time.time() * 1000),
        "operation": "ticket-cancel",
        "version": "3.0",
    }


def _partial_cashout_envelope(ticket_id: str, percentage: str, corr: str) -> dict[str, Any]:
    raw = _example_params_for("partial_cashout_with_aggregator")
    raw = {
        **raw,
        "ticket_id": ticket_id,
        "ticket_signature": "sig",
        "percentage": percentage,
        "payout_amount": "5",
        "cashout_id": f"co-{corr}",
        "correlation_id": corr,
    }
    result = build_cashout(
        "partial_cashout_with_aggregator", CashoutBuildParams.model_validate(raw)
    )
    return result.payload


@pytest.fixture
def busy_port() -> Generator[int]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield int(sock.getsockname()[1])


def _json_reply(raw: str | bytes) -> dict[str, Any]:
    text = raw.decode() if isinstance(raw, bytes) else raw
    return cast(dict[str, Any], json.loads(text))


def test_inject_event_literal_matches_catalog() -> None:
    assert tuple(sorted(get_args(InjectEvent))) == tuple(sorted(INJECT_EVENTS))


def test_expand_scenarios_bundle() -> None:
    expanded = expand_scenarios(["realistic_mix"])
    assert expanded.active == frozenset({"frame_split", "rate_limit"})


def test_start_and_stop_placement_roundtrip(mock_manager: MockServerManager) -> None:
    started = start_mock(mock_manager, scenarios=["realistic_mix"], ws_port=0, oauth_port=0)
    assert started["ok"] is True
    ws_url = str(started["ws_url"])

    async def _roundtrip() -> dict[str, Any]:
        payload = _placement_payload()
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(payload))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            return _json_reply(raw)

    reply = asyncio.run(_roundtrip())
    assert reply["content"]["type"] == "ticket-reply"
    assert reply["content"]["status"] == "accepted"

    stopped = stop_mock(mock_manager)
    assert stopped["ok"] is True
    assert len(stopped["wire_log"]) >= 2
    directions = [e["direction"] for e in stopped["wire_log"]]
    assert "outbound" in directions
    assert "inbound" in directions


def test_frame_split_rejects_oversized_single_frame(mock_manager: MockServerManager) -> None:
    started = start_mock(mock_manager, scenarios=["frame_split"], ws_port=0, oauth_port=0)
    ws_url = str(started["ws_url"])
    payload = _placement_payload()
    huge = json.dumps(payload) + (" " * (33 * 1024))

    async def _send() -> int | None:
        async with websockets.connect(ws_url) as ws:
            await ws.send(huge)
            try:
                await asyncio.wait_for(ws.wait_closed(), timeout=3)
            except TimeoutError:
                return None
            return ws.close_code

    close_code = asyncio.run(_send())
    stop_mock(mock_manager)
    assert close_code == 1009


def test_rate_limit_rejects_burst(mock_manager: MockServerManager) -> None:
    started = start_mock(
        mock_manager,
        scenarios=["rate_limit"],
        rate_limit_profile="integration",
        ws_port=0,
        oauth_port=0,
    )
    ws_url = str(started["ws_url"])
    payload = _placement_payload()

    async def _burst() -> list[dict[str, Any]]:
        replies: list[dict[str, Any]] = []
        async with websockets.connect(ws_url) as ws:
            for _ in range(15):
                await ws.send(json.dumps(payload))
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                replies.append(_json_reply(raw))
        return replies

    replies = asyncio.run(_burst())
    stopped = stop_mock(mock_manager)
    rejected = [r for r in replies if r["content"].get("status") == "rejected"]
    assert len(rejected) >= 3
    assert stopped["metrics"]["rate_limit_rejections"] >= 3


def test_alt_stake_offer_flow(mock_manager: MockServerManager) -> None:
    started = start_mock(mock_manager, scenarios=["alt_stake_offer"], ws_port=0, oauth_port=0)
    ws_url = str(started["ws_url"])
    first = _placement_payload()

    async def _flow() -> tuple[dict[str, Any], dict[str, Any]]:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(first))
            reject_raw = await asyncio.wait_for(ws.recv(), timeout=5)
            reject = _json_reply(reject_raw)
            sig = reject["content"]["signature"]
            ticket_id = reject["content"]["ticketId"]
            resubmit = json.loads(json.dumps(first))
            ctx = resubmit.setdefault("content", {}).setdefault("context", {})
            ctx["ref"] = {
                "type": "alt-stake",
                "ticketId": ticket_id,
                "ticketSignature": sig,
            }
            resubmit["correlationId"] = "resubmit-alt-stake"
            await ws.send(json.dumps(resubmit))
            accept_raw = await asyncio.wait_for(ws.recv(), timeout=5)
            return reject, _json_reply(accept_raw)

    reject, accept = asyncio.run(_flow())
    stop_mock(mock_manager)
    assert reject["content"]["status"] == "rejected"
    assert "altStake" in reject["content"]
    assert accept["content"]["status"] == "accepted"


def test_cancellation_matrix_accepts(mock_manager: MockServerManager) -> None:
    started = start_mock(mock_manager, scenarios=["cancellation_matrix"], ws_port=0, oauth_port=0)
    ws_url = str(started["ws_url"])
    ticket_id = _placement_payload()["content"]["ticketId"]

    async def _cancel(code: int) -> dict[str, Any]:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(_cancel_envelope(ticket_id, code)))
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            return _json_reply(raw)

    for code in (101, 103, 301):
        reply = asyncio.run(_cancel(code))
        assert reply["content"]["type"] == "cancel-reply"
        assert reply["content"]["status"] == "accepted"
    stop_mock(mock_manager)


def test_cancellation_matrix_reject_code_103(mock_manager: MockServerManager) -> None:
    started = start_mock(
        mock_manager,
        scenarios=["cancellation_matrix"],
        ws_port=0,
        oauth_port=0,
        scenario_params={"cancellation_matrix": {"reject_code_103": True}},
    )
    assert started["ok"] is True
    ticket_id = _placement_payload()["content"]["ticketId"]
    cancels = [_cancel_envelope(ticket_id, 103), _cancel_envelope(ticket_id, 101)]
    assert all(validate_request_payload(c).schema_ok for c in cancels)

    result = send_to_mock(mock_manager, messages=cancels)
    stop_mock(mock_manager)

    statuses = [ex["reply"]["content"]["status"] for ex in result["exchanges"]]
    assert statuses == ["rejected", "accepted"]


def test_partial_cashout_rejects_delta_percentage(mock_manager: MockServerManager) -> None:
    started = start_mock(
        mock_manager, scenarios=["partial_cashout_aggregator"], ws_port=0, oauth_port=0
    )
    ws_url = str(started["ws_url"])
    ticket_id = "cashout-ticket-1"

    def _cashout(pct: str, corr: str) -> dict[str, Any]:
        envelope = _partial_cashout_envelope(ticket_id, pct, corr)

        async def _send() -> dict[str, Any]:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps(envelope))
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                return _json_reply(raw)

        return asyncio.run(_send())

    first = _cashout("0.5", "c1")
    assert first["content"]["status"] == "accepted"
    bad = _cashout("0.3", "c2")
    assert bad["content"]["status"] == "rejected"
    good = _cashout("0.8", "c3")
    assert good["content"]["status"] == "accepted"
    stop_mock(mock_manager)


def test_cancel_and_cashout_replies_echo_request_ids(mock_manager: MockServerManager) -> None:
    started = start_mock(mock_manager, scenarios=["transaction_suite"], ws_port=0, oauth_port=0)
    assert started["ok"] is True
    cancel = _cancel_envelope("T-cancel", 101)
    cashout = _partial_cashout_envelope("T-cashout", "0.5", "corr-co")
    assert validate_request_payload(cancel).schema_ok
    assert validate_request_payload(cashout).schema_ok

    result = send_to_mock(mock_manager, messages=[cancel, cashout])
    stop_mock(mock_manager)

    cancel_reply, cashout_reply = (ex["reply"]["content"] for ex in result["exchanges"])
    assert cancel_reply["ticketId"] == "T-cancel"
    assert cancel_reply["cancellationId"] == "T-cancel"
    assert cashout_reply["ticketId"] == "T-cashout"
    assert cashout_reply["cashoutId"] == "co-corr-co"


def test_connection_blocked_inject(mock_manager: MockServerManager) -> None:
    started = start_mock(mock_manager, scenarios=["realistic_mix"], ws_port=0, oauth_port=0)
    ws_url = str(started["ws_url"])

    async def _try_send() -> bool:
        try:
            async with websockets.connect(ws_url, open_timeout=2) as ws:
                await ws.send(json.dumps(_placement_payload()))
                await asyncio.wait_for(ws.recv(), timeout=3)
                return True
        except (
            OSError,
            TimeoutError,
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.ConnectionClosedError,
            websockets.exceptions.ConnectionClosedOK,
        ):
            return False

    assert asyncio.run(_try_send()) is True
    blocked = inject_mock(mock_manager, "connection_blocked")
    assert blocked["ok"] is True
    assert asyncio.run(_try_send()) is False
    unblocked = inject_mock(mock_manager, "connection_unblocked")
    assert unblocked["ok"] is True
    assert asyncio.run(_try_send()) is True
    stop_mock(mock_manager)


def test_send_to_mock_placement_roundtrip(mock_manager: MockServerManager) -> None:
    started = start_mock(mock_manager, scenarios=["realistic_mix"], ws_port=0, oauth_port=0)
    assert started["ok"] is True

    result = send_to_mock(mock_manager, payload=_placement_payload())
    assert result["ok"] is True
    assert len(result["exchanges"]) == 1
    reply = result["exchanges"][0]["reply"]
    assert isinstance(reply, dict)
    assert reply["content"]["type"] == "ticket-reply"
    assert reply["content"]["status"] == "accepted"

    status = mock_manager.status()
    assert status["running"] is True
    assert status["ws_url"] == started["ws_url"]

    stopped = stop_mock(mock_manager)
    assert stopped["ok"] is True
    assert len(stopped["wire_log"]) >= 2


def test_send_to_mock_requires_running_mock(mock_manager: MockServerManager) -> None:
    with pytest.raises(MockServerError, match="start_mock"):
        send_to_mock(mock_manager, payload=_placement_payload())


def test_send_to_mock_alt_stake_multi_message(mock_manager: MockServerManager) -> None:
    started = start_mock(mock_manager, scenarios=["alt_stake_offer"], ws_port=0, oauth_port=0)
    assert started["ok"] is True
    first = _placement_payload()

    reject_result = send_to_mock(mock_manager, payload=first)
    assert reject_result["ok"] is True
    reject = reject_result["exchanges"][0]["reply"]
    assert isinstance(reject, dict)
    assert reject["content"]["status"] == "rejected"

    resubmit = json.loads(json.dumps(first))
    ctx = resubmit.setdefault("content", {}).setdefault("context", {})
    ctx["ref"] = {
        "type": "alt-stake",
        "ticketId": reject["content"]["ticketId"],
        "ticketSignature": reject["content"]["signature"],
    }
    resubmit["correlationId"] = "resubmit-alt-stake"

    accept_result = send_to_mock(
        mock_manager,
        messages=[first, resubmit],
        reuse_connection=True,
    )
    assert accept_result["ok"] is True
    assert len(accept_result["exchanges"]) == 2
    assert accept_result["exchanges"][0]["reply"]["content"]["status"] == "rejected"
    assert accept_result["exchanges"][1]["reply"]["content"]["status"] == "accepted"
    stop_mock(mock_manager)


def test_start_mock_on_busy_ws_port_returns_error_and_allows_restart(
    mock_manager: MockServerManager,
    busy_port: int,
) -> None:
    with pytest.raises(MockServerError, match="failed to start"):
        start_mock(mock_manager, scenarios=["frame_split"], ws_port=busy_port, oauth_port=0)
    assert mock_manager.is_running is False

    restarted = start_mock(mock_manager, scenarios=["frame_split"], ws_port=0, oauth_port=0)
    assert restarted["ok"] is True
    stop_mock(mock_manager)


def test_start_mock_on_busy_oauth_port_releases_ws_port(
    mock_manager: MockServerManager,
    busy_port: int,
) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        ws_port = int(probe.getsockname()[1])

    with pytest.raises(MockServerError):
        start_mock(mock_manager, scenarios=["frame_split"], ws_port=ws_port, oauth_port=busy_port)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", ws_port))


def test_unknown_scenario_fails(mock_manager: MockServerManager) -> None:
    with pytest.raises(MockServerError, match="Unknown scenario"):
        start_mock(mock_manager, scenarios=["not_a_scenario"], ws_port=0)
