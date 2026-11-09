"""Wire log and per-session metrics for the local simulator."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

Direction = Literal["outbound", "inbound"]


@dataclass
class WireEntry:
    direction: Direction
    message: dict[str, Any]
    timestamp_utc_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_session_state_entry(self) -> dict[str, Any]:
        return {"direction": self.direction, "message": self.message}


@dataclass
class ReconnectRecord:
    timestamp_utc_ms: int
    remote_address: str


@dataclass
class MockMetrics:
    messages_in: int = 0
    messages_out: int = 0
    rate_limit_rejections: int = 0
    connections: int = 0
    reconnect_attempts: list[ReconnectRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages_in": self.messages_in,
            "messages_out": self.messages_out,
            "rate_limit_rejections": self.rate_limit_rejections,
            "connections": self.connections,
            "reconnect_attempts": [
                {"timestamp_utc_ms": r.timestamp_utc_ms, "remote_address": r.remote_address}
                for r in self.reconnect_attempts
            ],
        }


@dataclass
class ConnectionState:
    """Per-WebSocket connection mutable state for reactive scenarios."""

    placement_count: int = 0
    ticket_signatures: dict[str, str] = field(default_factory=dict)
    cashout_cumulative_pct: dict[str, float] = field(default_factory=dict)
    placed_ticket_ids: set[str] = field(default_factory=set)


@dataclass
class MockSession:
    session_id: str
    started_at: float
    scenarios_active: frozenset[str]
    wire_log: list[WireEntry] = field(default_factory=list)
    metrics: MockMetrics = field(default_factory=MockMetrics)
    global_ticket_signatures: dict[str, str] = field(default_factory=dict)
    global_cashout_pct: dict[str, float] = field(default_factory=dict)

    def log_outbound(self, message: dict[str, Any]) -> None:
        self.wire_log.append(WireEntry(direction="outbound", message=message))
        self.metrics.messages_in += 1

    def log_inbound(self, message: dict[str, Any]) -> None:
        self.wire_log.append(WireEntry(direction="inbound", message=message))
        self.metrics.messages_out += 1

    def wire_log_as_session_state(self) -> list[dict[str, Any]]:
        return [entry.to_session_state_entry() for entry in self.wire_log]

    def duration_seconds(self) -> float:
        return time.time() - self.started_at
