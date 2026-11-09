"""Ticket context rules: alt-stake ref, end customer, channel, and inform validations."""

from __future__ import annotations

import re
from typing import Any

from mts_client_integration.models.business_rules import (
    CHANNEL_CI_EXPECTATIONS,
    ISO_639_1_CODES,
    BusinessRuleIssue,
)
from mts_client_integration.services.business_rules.inputs import TicketRuleInput
from mts_client_integration.services.ticket_tree import (
    as_dict,
    as_list,
    as_str,
)

_ALPHANUMERIC_RE = re.compile(r"^[A-Za-z0-9]+$")


def check_context(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    issues: list[BusinessRuleIssue] = []
    context = as_dict(ctx.ticket.get("context"))
    if context is None:
        return issues
    issues.extend(_check_ref(context))
    issues.extend(_check_end_customer(context))
    issues.extend(_check_channel(context))
    return issues


def _check_ref(context: dict[str, Any]) -> list[BusinessRuleIssue]:
    ref = as_dict(context.get("ref"))
    if ref is None:
        return []
    missing = [f for f in ("type", "ticketId", "ticketSignature") if not ref.get(f)]
    ref_type = ref.get("type")
    issues: list[BusinessRuleIssue] = []
    if missing:
        issues.append(
            BusinessRuleIssue(
                "ref_alt_stake_reoffer",
                "error",
                "$.content.context.ref",
                f"Alt-stake/reoffer 'ref' is missing required fields: {missing}.",
                maps_to_code=-210,
            )
        )
    elif ref_type not in {"alt-stake", "reoffer"}:
        issues.append(
            BusinessRuleIssue(
                "ref_alt_stake_reoffer",
                "error",
                "$.content.context.ref.type",
                f"ref.type {ref_type!r} must be 'alt-stake' or 'reoffer'.",
                maps_to_code=-210,
            )
        )
    return issues


def _check_end_customer(context: dict[str, Any]) -> list[BusinessRuleIssue]:
    end_customer = as_dict(context.get("endCustomer"))
    if end_customer is None:
        return []
    customer_id = as_str(end_customer.get("id"))
    if customer_id is None:
        return []
    if not _ALPHANUMERIC_RE.match(customer_id):
        return [
            BusinessRuleIssue(
                "end_customer_id_alphanumeric",
                "warning",
                "$.content.context.endCustomer.id",
                f"endCustomer.id {customer_id!r} should be alphanumeric and free of personal data.",
                maps_to_code=-106,
            )
        ]
    return []


def _check_channel(context: dict[str, Any]) -> list[BusinessRuleIssue]:
    channel = as_dict(context.get("channel"))
    if channel is None:
        return []
    issues: list[BusinessRuleIssue] = []
    channel_type = as_str(channel.get("type"))
    lang = as_str(channel.get("lang"))
    if lang is not None and lang.lower() not in ISO_639_1_CODES:
        issues.append(
            BusinessRuleIssue(
                "language_iso639",
                "warning",
                "$.content.context.channel.lang",
                f"channel.lang {lang!r} is not a recognised ISO 639-1 code.",
            )
        )
    expectation = CHANNEL_CI_EXPECTATIONS.get(channel_type or "")
    if expectation is not None:
        missing = [f for f in expectation.required_fields if not channel.get(f)]
        if missing:
            issues.append(
                BusinessRuleIssue(
                    "channel_ci_mandatory_fields",
                    "warning",
                    "$.content.context.channel",
                    f"Channel {channel_type!r} is missing CI-expected field(s): {missing}.",
                )
            )
        if expectation.needs_end_customer and not as_dict(context.get("endCustomer")):
            issues.append(
                BusinessRuleIssue(
                    "channel_ci_mandatory_fields",
                    "warning",
                    "$.content.context.endCustomer",
                    f"Channel {channel_type!r} typically requires endCustomer.id "
                    "for registered bets.",
                )
            )
    return issues


def check_inform_bet_validations(ctx: TicketRuleInput) -> list[BusinessRuleIssue]:
    if ctx.operation != "ticket-placement-inform":
        return []
    validations = as_list(ctx.content.get("betValidations"))
    if not validations:
        return [
            BusinessRuleIssue(
                "prevalidated_inform_bet_validations",
                "error",
                "$.content.betValidations",
                "ticket-placement-inform requires a non-empty betValidations array.",
            )
        ]
    issues: list[BusinessRuleIssue] = []
    for index, entry in enumerate(validations):
        if not isinstance(entry, dict) or "code" not in entry:
            issues.append(
                BusinessRuleIssue(
                    "prevalidated_inform_bet_validations",
                    "error",
                    f"$.content.betValidations[{index}]",
                    "Each betValidations entry must include a 'code' field.",
                )
            )
    return issues
