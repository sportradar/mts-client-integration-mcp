"""Low-level helpers that assemble Ticket 3.0 request JSON from typed params."""

from __future__ import annotations

import time
import uuid
from typing import Any

from mts_client_integration.models.templates import (
    BetBuildParams,
    BetType,
    CashoutBuildParams,
    ChannelParams,
    ExtSettlementBuildParams,
    PlacementBuildParams,
    RefParams,
    SelectionParams,
)
from mts_client_integration.services.composite_selections import (
    build_composite_bet_selections,
    uses_composite_selections,
)
from mts_client_integration.services.feed_selections import build_feed_selection, require


def new_id(prefix: str = "") -> str:
    token = uuid.uuid4().hex[:12]
    return f"{prefix}{token}" if prefix else token


def _timestamp_utc_ms(requested: int | None) -> int:
    return int(time.time() * 1000) if requested is None else requested


def _envelope(
    *,
    operator_id: str,
    content: dict[str, Any],
    operation: str,
    correlation_id: str | None,
    timestamp_utc_ms: int | None,
) -> dict[str, Any]:
    return {
        "operatorId": operator_id,
        "content": content,
        "correlationId": correlation_id or new_id("corr-"),
        "timestampUtc": _timestamp_utc_ms(timestamp_utc_ms),
        "operation": operation,
        "version": "3.0",
    }


def build_channel(channel: ChannelParams) -> dict[str, Any]:
    node: dict[str, Any] = {"type": channel.type, "lang": channel.lang}
    if channel.ip:
        node["ip"] = channel.ip
    if channel.shop_id is not None:
        node["shopId"] = channel.shop_id
    if channel.terminal_id is not None:
        node["terminalId"] = channel.terminal_id
    if channel.device_id is not None:
        node["deviceId"] = channel.device_id
    return node


def _stake(amount: str, currency: str) -> list[dict[str, Any]]:
    return [{"type": "cash", "currency": currency, "amount": amount}]


def assemble_selections(
    selections: list[SelectionParams],
    *,
    bet_type: BetType,
    size: list[int] | None,
    banker_selection_indexes: list[int],
    custom_bet_odds: str | None,
) -> list[dict[str, Any]]:
    feed_selections = [build_feed_selection(sel) for sel in selections]
    if banker_selection_indexes and bet_type != "system":
        msg = f"banker_selection_indexes is only supported for bet_type 'system', not {bet_type!r}"
        raise ValueError(msg)

    if bet_type == "single":
        if len(feed_selections) != 1:
            msg = "single bet type requires exactly one selection"
            raise ValueError(msg)
        return feed_selections

    if bet_type == "accumulator":
        if len(feed_selections) < 2:
            msg = "accumulator requires at least two selections"
            raise ValueError(msg)
        return [{"type": "accumulator", "selections": feed_selections}]

    if bet_type == "ways":
        if len(feed_selections) < 2:
            msg = "ways requires at least two selections"
            raise ValueError(msg)
        return [{"type": "ways", "selections": feed_selections}]

    if bet_type == "custom_bet":
        if len(feed_selections) < 2:
            msg = "custom_bet requires at least two inner selections"
            raise ValueError(msg)
        if not custom_bet_odds:
            msg = "custom_bet requires custom_bet_odds"
            raise ValueError(msg)
        return [
            {
                "type": "uf-custom-bet",
                "selections": feed_selections,
                "odds": {"type": "decimal", "value": custom_bet_odds},
            }
        ]

    if bet_type == "system":
        if size is None:
            msg = "system bet type requires size"
            raise ValueError(msg)
        if len(feed_selections) < 2:
            msg = "system requires at least two selections"
            raise ValueError(msg)
        _validate_banker_indexes(banker_selection_indexes, len(feed_selections))
        banker_set = set(banker_selection_indexes)
        system_selections: list[dict[str, Any]] = []
        banker_selections: list[dict[str, Any]] = []
        for index, feed in enumerate(feed_selections):
            if index in banker_set:
                banker_selections.append(feed)
            else:
                system_selections.append(feed)
        if not system_selections:
            msg = "system bet cannot mark every selection as a banker"
            raise ValueError(msg)
        bet_selections: list[dict[str, Any]] = [
            {"type": "system", "size": size, "selections": system_selections}
        ]
        bet_selections.extend(banker_selections)
        return bet_selections

    msg = f"unsupported bet type: {bet_type}"
    raise ValueError(msg)


def _validate_banker_indexes(indexes: list[int], selection_count: int) -> None:
    if len(set(indexes)) != len(indexes):
        msg = f"banker_selection_indexes contains duplicates: {indexes}"
        raise ValueError(msg)
    out_of_range = [index for index in indexes if not 0 <= index < selection_count]
    if out_of_range:
        msg = (
            f"banker_selection_indexes {out_of_range} out of range for "
            f"{selection_count} selections (valid: 0..{selection_count - 1})"
        )
        raise ValueError(msg)


def build_bet(
    bet: BetBuildParams,
    *,
    default_bet_type: BetType,
    default_size: list[int] | None,
    default_stake: str,
    default_currency: str,
) -> dict[str, Any]:
    bet_type = bet.bet_type or default_bet_type
    size = bet.size if bet.size is not None else default_size
    return {
        "selections": assemble_selections(
            bet.selections,
            bet_type=bet_type,
            size=size,
            banker_selection_indexes=bet.banker_selection_indexes,
            custom_bet_odds=bet.custom_bet_odds,
        ),
        "stake": _stake(bet.stake or default_stake, bet.currency or default_currency),
    }


def build_placement_envelope(params: PlacementBuildParams) -> dict[str, Any]:
    if params.bets is not None:
        bets = [
            build_bet(
                bet,
                default_bet_type=params.bet_type,
                default_size=params.size,
                default_stake=params.stake,
                default_currency=params.currency,
            )
            for bet in params.bets
        ]
    else:
        selections = require(params.selections, "selections")
        if uses_composite_selections(params):
            selection_tree = build_composite_bet_selections(params)
        else:
            selection_tree = assemble_selections(
                selections,
                bet_type=params.bet_type,
                size=params.size,
                banker_selection_indexes=params.banker_selection_indexes,
                custom_bet_odds=params.custom_bet_odds,
            )
        bets = [
            {
                "selections": selection_tree,
                "stake": _stake(params.stake, params.currency),
            }
        ]

    context: dict[str, Any] = {
        "channel": build_channel(params.channel),
        "limitId": params.limit_id,
    }
    if params.end_customer_id is not None:
        context["endCustomer"] = {"id": params.end_customer_id}
    if params.ref is not None:
        context["ref"] = _ref_dict(params.ref)

    content: dict[str, Any] = {
        "type": "ticket",
        "ticketId": params.ticket_id or new_id("t-"),
        "bets": bets,
        "context": context,
    }

    return _envelope(
        operator_id=params.operator_id,
        content=content,
        operation="ticket-placement",
        correlation_id=params.correlation_id,
        timestamp_utc_ms=params.timestamp_utc_ms,
    )


def build_cashout_envelope(params: CashoutBuildParams) -> dict[str, Any]:
    if params.partial:
        details: dict[str, Any] = {
            "type": "ticket-partial",
            "ticketId": params.ticket_id,
            "ticketSignature": params.ticket_signature,
            "code": params.code,
            "percentage": params.percentage,
            "payout": _stake(params.payout_amount, params.currency),
        }
    else:
        details = {
            "type": "ticket",
            "ticketId": params.ticket_id,
            "ticketSignature": params.ticket_signature,
            "code": params.code,
            "payout": _stake(params.payout_amount, params.currency),
        }

    content: dict[str, Any] = {"type": "cashout", "details": details}
    if params.cashout_id is not None:
        content["cashoutId"] = params.cashout_id

    return _envelope(
        operator_id=params.operator_id,
        content=content,
        operation="ticket-cashout",
        correlation_id=params.correlation_id,
        timestamp_utc_ms=params.timestamp_utc_ms,
    )


def build_ext_settlement_envelope(params: ExtSettlementBuildParams) -> dict[str, Any]:
    payout_line: dict[str, Any] = {
        "type": "cash",
        "currency": params.currency,
        "amount": params.payout_amount,
    }
    if params.trace_id is not None:
        payout_line["traceId"] = params.trace_id

    details: dict[str, Any] = {
        "type": params.settlement_level,
        "ticketId": params.ticket_id,
        "ticketSignature": params.ticket_signature,
        "payout": [payout_line],
    }
    if params.settlement_level == "bet":
        details["betId"] = require(params.bet_id, "bet_id")

    content: dict[str, Any] = {
        "type": "ext-settlement",
        "settlementId": params.settlement_id or new_id("SETL"),
        "details": details,
    }

    return _envelope(
        operator_id=params.operator_id,
        content=content,
        operation="ticket-ext-settlement",
        correlation_id=params.correlation_id,
        timestamp_utc_ms=params.timestamp_utc_ms,
    )


def _ref_dict(ref: RefParams) -> dict[str, Any]:
    return {
        "type": ref.type,
        "ticketId": ref.ticket_id,
        "ticketSignature": ref.ticket_signature,
    }
