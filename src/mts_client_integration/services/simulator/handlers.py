"""Message routing and scenario-specific response logic."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from mts_client_integration.services.simulator.fixtures import (
    build_cancel_reply,
    build_cashout_reply,
    build_rate_limit_rejection,
    build_ticket_accepted,
    build_ticket_rejected,
    default_alt_stake_amount,
    parse_cashout_percentage,
    request_ticket_id,
)
from mts_client_integration.services.simulator.session import ConnectionState, MockSession
from mts_client_integration.services.ticket_tree import as_dict


class RateLimiter:
    """Token-bucket rate limiter."""

    def __init__(
        self,
        rps: float,
        *,
        burst: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rps = rps
        self._burst = float(burst if burst is not None else max(int(rps), 1))
        self._tokens = self._burst
        self._clock = clock
        self._last_mono: float | None = None

    def allow(self) -> bool:
        now = self._clock()
        elapsed = 0.0 if self._last_mono is None else now - self._last_mono
        self._last_mono = now
        self._tokens = min(self._burst, self._tokens + elapsed * self._rps)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


class MessageHandler:
    """Produce fixture replies for inbound Ticket 3.0 requests."""

    def __init__(
        self,
        session: MockSession,
        *,
        scenario_params: dict[str, dict[str, Any]] | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._session = session
        self._params = scenario_params or {}
        self._rate_limiter = rate_limiter
        self._active = session.scenarios_active

    def handle(self, envelope: dict[str, Any], conn: ConnectionState) -> dict[str, Any] | None:
        operation = envelope.get("operation")
        if not isinstance(operation, str):
            return None

        if (
            "rate_limit" in self._active
            and self._rate_limiter is not None
            and not self._rate_limiter.allow()
        ):
            self._session.metrics.rate_limit_rejections += 1
            return build_rate_limit_rejection(envelope)

        if operation == "ticket-placement":
            return self._handle_placement(envelope, conn)
        if operation == "ticket-cancel":
            return self._handle_cancel(envelope)
        if operation == "ticket-cashout":
            return self._handle_cashout(envelope, conn)
        if operation.endswith("-ack") or operation.endswith("-inform"):
            return None
        return build_ticket_accepted(envelope)

    def _handle_placement(
        self,
        envelope: dict[str, Any],
        conn: ConnectionState,
    ) -> dict[str, Any]:
        if "alt_stake_offer" not in self._active:
            reply = build_ticket_accepted(envelope)
            self._remember_placement(envelope, reply, conn)
            return reply

        content = as_dict(envelope.get("content")) or {}
        context = as_dict(content.get("context")) or {}
        ref = as_dict(context.get("ref"))
        if ref and ref.get("type") == "alt-stake":
            reply = build_ticket_accepted(envelope)
            self._remember_placement(envelope, reply, conn)
            return reply

        if conn.placement_count > 0:
            reply = build_ticket_accepted(envelope)
            self._remember_placement(envelope, reply, conn)
            return reply

        conn.placement_count += 1
        params = self._params.get("alt_stake_offer", {})
        reject_code = int(params.get("reject_code", -702))
        message = str(params.get("message", "Bet liability exceeded (mock alt-stake)"))
        alt_stake = params.get("suggested_stake")
        if not isinstance(alt_stake, dict):
            alt_stake = default_alt_stake_amount(envelope)
        reply = build_ticket_rejected(
            envelope,
            code=reject_code,
            message=message,
            alt_stake=alt_stake,
        )
        sig = reply["content"]["signature"]
        if isinstance(sig, str):
            ticket_id = _ticket_id(envelope)
            conn.ticket_signatures[ticket_id] = sig
            self._session.global_ticket_signatures[ticket_id] = sig
        return reply

    def _handle_cancel(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if "cancellation_matrix" not in self._active:
            return build_cancel_reply(envelope, accepted=True)

        content = as_dict(envelope.get("content")) or {}
        details = as_dict(content.get("details")) or {}
        code = details.get("code")
        params = self._params.get("cancellation_matrix", {})
        reject_103 = bool(params.get("reject_code_103", False))
        if reject_103 and code == 103:
            return build_cancel_reply(envelope, accepted=False)
        return build_cancel_reply(envelope, accepted=True)

    def _handle_cashout(
        self,
        envelope: dict[str, Any],
        conn: ConnectionState,
    ) -> dict[str, Any]:
        if "partial_cashout_aggregator" not in self._active:
            return build_cashout_reply(envelope, accepted=True)

        ticket_id = _ticket_id(envelope)
        pct = parse_cashout_percentage(envelope)
        if pct is None:
            return build_cashout_reply(
                envelope,
                accepted=False,
                code=-1,
                message="Missing or invalid percentage",
            )

        prior = conn.cashout_cumulative_pct.get(
            ticket_id,
            self._session.global_cashout_pct.get(ticket_id, 0.0),
        )
        pct_f = float(pct)

        if abs(prior - 0.5) < 0.001 and abs(pct_f - 0.3) < 0.001:
            return build_cashout_reply(
                envelope,
                accepted=False,
                code=-1,
                message=(
                    "Second partial cashout sent with delta percentage 0.3; "
                    "MTS expects cumulative 0.8 after a 0.5 cashout"
                ),
            )

        if pct_f <= prior:
            return build_cashout_reply(
                envelope,
                accepted=False,
                code=-1,
                message="Cumulative cashout percentage must increase",
            )

        conn.cashout_cumulative_pct[ticket_id] = pct_f
        self._session.global_cashout_pct[ticket_id] = pct_f
        return build_cashout_reply(envelope, accepted=True)

    def _remember_placement(
        self,
        envelope: dict[str, Any],
        reply: dict[str, Any],
        conn: ConnectionState,
    ) -> None:
        ticket_id = _ticket_id(envelope)
        conn.placed_ticket_ids.add(ticket_id)
        content = reply.get("content")
        if isinstance(content, dict):
            sig = content.get("signature")
            if isinstance(sig, str):
                conn.ticket_signatures[ticket_id] = sig
                self._session.global_ticket_signatures[ticket_id] = sig


def _ticket_id(envelope: dict[str, Any]) -> str:
    return request_ticket_id(envelope) or "unknown"
