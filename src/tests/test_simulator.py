"""Tests for the targeted local MTS simulator (MVP capability #4)."""

from __future__ import annotations

import asyncio
import copy
import functools
import json
import socket
from typing import Any, cast, get_args

import pytest
import websockets

from mts_client_integration.models.templates import CashoutBuildParams
from mts_client_integration.services.simulator import server as server_module
from mts_client_integration.services.simulator.catalog import (
    INJECT_EVENTS,
    InjectEvent,
    expand_scenarios,
)
from mts_client_integration.services.simulator.handlers import RateLimiter
from mts_client_integration.services.simulator.server import MockServerError, MockServerManager
from mts_client_integration.services.template_builder import build_cashout
from mts_client_integration.services.validation import validate_request_payload
from mts_client_integration.tools.mock_server import (
    inject_mock,
    send_to_mock,
    start_mock,
    stop_mock,
)
from tests.factories import FIXED_TIMESTAMP_MS, example_params_for, placement_payload

_REPLY_TIMEOUT_SECONDS = 5


def _start(manager: MockServerManager, *scenarios: str, **kwargs: Any) -> str:
    """Start the mock on ephemeral ports and return its ``ws_url``."""
    started = start_mock(manager, scenarios=list(scenarios), ws_port=0, oauth_port=0, **kwargs)
    assert started["ok"] is True
    return str(started["ws_url"])


def _ws_exchange(ws_url: str, frames: list[str]) -> list[dict[str, Any]]:
    """Send raw frames on one WebSocket connection, returning one JSON reply per frame."""

    async def _run() -> list[dict[str, Any]]:
        replies: list[dict[str, Any]] = []
        async with websockets.connect(ws_url) as ws:
            for frame in frames:
                await ws.send(frame)
                raw = await asyncio.wait_for(ws.recv(), timeout=_REPLY_TIMEOUT_SECONDS)
                text = raw.decode() if isinstance(raw, bytes) else raw
                replies.append(cast(dict[str, Any], json.loads(text)))
        return replies

    return asyncio.run(_run())


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
        "timestampUtc": FIXED_TIMESTAMP_MS,
        "operation": "ticket-cancel",
        "version": "3.0",
    }


def _partial_cashout_envelope(ticket_id: str, percentage: str, corr: str) -> dict[str, Any]:
    raw = {
        **example_params_for("partial_cashout_with_aggregator"),
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


def _alt_stake_resubmit(first: dict[str, Any], reject: dict[str, Any]) -> dict[str, Any]:
    """Resubmit ``first`` referencing the alt-stake offer carried by ``reject``."""
    resubmit = copy.deepcopy(first)
    resubmit["content"]["context"]["ref"] = {
        "type": "alt-stake",
        "ticketId": reject["content"]["ticketId"],
        "ticketSignature": reject["content"]["signature"],
    }
    resubmit["correlationId"] = "resubmit-alt-stake"
    return resubmit


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #


def test_inject_event_literal_matches_catalog() -> None:
    assert tuple(sorted(get_args(InjectEvent))) == tuple(sorted(INJECT_EVENTS))


def test_expand_scenarios_bundle() -> None:
    expanded = expand_scenarios(["realistic_mix"])
    assert expanded.active == frozenset({"frame_split", "rate_limit"})


# --------------------------------------------------------------------------- #
# Rate limiter (token bucket)
# --------------------------------------------------------------------------- #


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_rate_limiter_allows_burst_then_rejects() -> None:
    limiter = RateLimiter(10.0, burst=3, clock=_FakeClock())
    assert [limiter.allow() for _ in range(4)] == [True, True, True, False]


def test_rate_limiter_refills_at_rps() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(10.0, burst=1, clock=clock)
    assert limiter.allow() is True
    clock.now += 0.05
    assert limiter.allow() is False
    clock.now += 0.05
    assert limiter.allow() is True


def test_rate_limiter_refill_is_capped_at_burst() -> None:
    clock = _FakeClock()
    limiter = RateLimiter(10.0, burst=2, clock=clock)
    limiter.allow()
    clock.now += 60
    assert [limiter.allow() for _ in range(3)] == [True, True, False]


def test_rate_limiter_default_burst_equals_rps() -> None:
    limiter = RateLimiter(5.0, clock=_FakeClock())
    assert sum(limiter.allow() for _ in range(10)) == 5


# --------------------------------------------------------------------------- #
# Wire behaviour (real WebSocket against the background mock)
# --------------------------------------------------------------------------- #


def test_start_and_stop_placement_roundtrip(mock_manager: MockServerManager) -> None:
    ws_url = _start(mock_manager, "realistic_mix")

    (reply,) = _ws_exchange(ws_url, [json.dumps(placement_payload())])
    assert reply["content"]["type"] == "ticket-reply"
    assert reply["content"]["status"] == "accepted"

    stopped = stop_mock(mock_manager)
    assert stopped["ok"] is True
    assert [e["direction"] for e in stopped["wire_log"]] == ["outbound", "inbound"]


def test_frame_split_rejects_oversized_single_frame(mock_manager: MockServerManager) -> None:
    ws_url = _start(mock_manager, "frame_split")
    huge = json.dumps(placement_payload()) + (" " * (33 * 1024))

    async def _send() -> int | None:
        async with websockets.connect(ws_url) as ws:
            await ws.send(huge)
            try:
                await asyncio.wait_for(ws.wait_closed(), timeout=3)
            except TimeoutError:
                return None
            return ws.close_code

    assert asyncio.run(_send()) == 1009


def test_rate_limit_rejects_burst(
    mock_manager: MockServerManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen = functools.partial(RateLimiter, clock=lambda: 0.0)
    monkeypatch.setattr(server_module, "RateLimiter", frozen)
    ws_url = _start(mock_manager, "rate_limit", rate_limit_profile="integration")

    replies = _ws_exchange(ws_url, [json.dumps(placement_payload())] * 15)
    stopped = stop_mock(mock_manager)

    statuses = [r["content"]["status"] for r in replies]
    # Integration profile is 10 r/s with burst 10; a frozen clock never refills.
    assert statuses == ["accepted"] * 10 + ["rejected"] * 5
    assert stopped["metrics"]["rate_limit_rejections"] == 5


def test_alt_stake_offer_flow(mock_manager: MockServerManager) -> None:
    ws_url = _start(mock_manager, "alt_stake_offer")
    first = placement_payload()

    async def _flow() -> tuple[dict[str, Any], dict[str, Any]]:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(first))
            reject = json.loads(await asyncio.wait_for(ws.recv(), _REPLY_TIMEOUT_SECONDS))
            await ws.send(json.dumps(_alt_stake_resubmit(first, reject)))
            accept = json.loads(await asyncio.wait_for(ws.recv(), _REPLY_TIMEOUT_SECONDS))
            return reject, accept

    reject, accept = asyncio.run(_flow())
    assert reject["content"]["status"] == "rejected"
    assert "altStake" in reject["content"]
    assert accept["content"]["status"] == "accepted"


@pytest.mark.parametrize("code", [101, 103, 301])
def test_cancellation_matrix_accepts(mock_manager: MockServerManager, code: int) -> None:
    ws_url = _start(mock_manager, "cancellation_matrix")
    ticket_id = placement_payload()["content"]["ticketId"]

    (reply,) = _ws_exchange(ws_url, [json.dumps(_cancel_envelope(ticket_id, code))])
    assert reply["content"]["type"] == "cancel-reply"
    assert reply["content"]["status"] == "accepted"


def test_cancellation_matrix_reject_code_103(mock_manager: MockServerManager) -> None:
    _start(
        mock_manager,
        "cancellation_matrix",
        scenario_params={"cancellation_matrix": {"reject_code_103": True}},
    )
    ticket_id = placement_payload()["content"]["ticketId"]
    cancels = [_cancel_envelope(ticket_id, 103), _cancel_envelope(ticket_id, 101)]
    assert all(validate_request_payload(c).schema_ok for c in cancels)

    result = send_to_mock(mock_manager, messages=cancels)

    statuses = [ex["reply"]["content"]["status"] for ex in result["exchanges"]]
    assert statuses == ["rejected", "accepted"]


def test_partial_cashout_rejects_delta_percentage(mock_manager: MockServerManager) -> None:
    _start(mock_manager, "partial_cashout_aggregator")
    ticket_id = "cashout-ticket-1"
    cashouts = [
        _partial_cashout_envelope(ticket_id, "0.5", "c1"),
        _partial_cashout_envelope(ticket_id, "0.3", "c2"),
        _partial_cashout_envelope(ticket_id, "0.8", "c3"),
    ]

    result = send_to_mock(mock_manager, messages=cashouts, reuse_connection=False)

    statuses = [ex["reply"]["content"]["status"] for ex in result["exchanges"]]
    assert statuses == ["accepted", "rejected", "accepted"]


def test_cancel_and_cashout_replies_echo_request_ids(mock_manager: MockServerManager) -> None:
    _start(mock_manager, "transaction_suite")
    cancel = _cancel_envelope("T-cancel", 101)
    cashout = _partial_cashout_envelope("T-cashout", "0.5", "corr-co")
    assert validate_request_payload(cancel).schema_ok
    assert validate_request_payload(cashout).schema_ok

    result = send_to_mock(mock_manager, messages=[cancel, cashout])

    cancel_reply, cashout_reply = (ex["reply"]["content"] for ex in result["exchanges"])
    assert cancel_reply["ticketId"] == "T-cancel"
    assert cancel_reply["cancellationId"] == "T-cancel"
    assert cashout_reply["ticketId"] == "T-cashout"
    assert cashout_reply["cashoutId"] == "co-corr-co"


def test_connection_blocked_inject(mock_manager: MockServerManager) -> None:
    ws_url = _start(mock_manager, "realistic_mix")

    async def _try_send() -> bool:
        try:
            async with websockets.connect(ws_url, open_timeout=2) as ws:
                await ws.send(json.dumps(placement_payload()))
                await asyncio.wait_for(ws.recv(), timeout=3)
                return True
        except OSError, TimeoutError, websockets.exceptions.ConnectionClosed:
            return False

    assert asyncio.run(_try_send()) is True
    assert inject_mock(mock_manager, "connection_blocked")["ok"] is True
    assert asyncio.run(_try_send()) is False
    assert inject_mock(mock_manager, "connection_unblocked")["ok"] is True
    assert asyncio.run(_try_send()) is True


# --------------------------------------------------------------------------- #
# send_to_mock helper and manager lifecycle
# --------------------------------------------------------------------------- #


def test_send_to_mock_placement_roundtrip(mock_manager: MockServerManager) -> None:
    ws_url = _start(mock_manager, "realistic_mix")

    result = send_to_mock(mock_manager, payload=placement_payload())
    assert result["ok"] is True
    (exchange,) = result["exchanges"]
    assert exchange["reply"]["content"]["type"] == "ticket-reply"
    assert exchange["reply"]["content"]["status"] == "accepted"

    status = mock_manager.status()
    assert status["running"] is True
    assert status["ws_url"] == ws_url

    stopped = stop_mock(mock_manager)
    assert [e["direction"] for e in stopped["wire_log"]] == ["outbound", "inbound"]


def test_send_to_mock_requires_running_mock(mock_manager: MockServerManager) -> None:
    with pytest.raises(MockServerError, match="start_mock"):
        send_to_mock(mock_manager, payload=placement_payload())


def test_send_to_mock_alt_stake_multi_message(mock_manager: MockServerManager) -> None:
    _start(mock_manager, "alt_stake_offer")
    first = placement_payload()

    (probe,) = send_to_mock(mock_manager, payload=first)["exchanges"]
    resubmit = _alt_stake_resubmit(first, probe["reply"])

    result = send_to_mock(mock_manager, messages=[first, resubmit], reuse_connection=True)

    statuses = [ex["reply"]["content"]["status"] for ex in result["exchanges"]]
    assert statuses == ["rejected", "accepted"]


def test_start_mock_on_busy_ws_port_returns_error_and_allows_restart(
    mock_manager: MockServerManager,
    busy_port: int,
) -> None:
    with pytest.raises(MockServerError, match="failed to start"):
        start_mock(mock_manager, scenarios=["frame_split"], ws_port=busy_port, oauth_port=0)
    assert mock_manager.is_running is False

    _start(mock_manager, "frame_split")
    assert mock_manager.is_running is True


def test_start_mock_on_busy_oauth_port_releases_ws_port(
    mock_manager: MockServerManager,
    busy_port: int,
) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        ws_port = int(probe.getsockname()[1])

    with pytest.raises(MockServerError):
        start_mock(mock_manager, scenarios=["frame_split"], ws_port=ws_port, oauth_port=busy_port)

    # Rebinding only succeeds if the failed start closed the WS listener it had opened.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", ws_port))
        assert sock.getsockname()[1] == ws_port


def test_unknown_scenario_fails(mock_manager: MockServerManager) -> None:
    with pytest.raises(MockServerError, match="Unknown scenario"):
        start_mock(mock_manager, scenarios=["not_a_scenario"], ws_port=0)
