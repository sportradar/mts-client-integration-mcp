"""Business-rule orchestration for outbound Ticket 3.0 requests.

Each rule is a small pure function over the raw payload dict. Rules are registered
in ``ENVELOPE_RULES`` / ``TICKET_RULES`` (order is the order of reported issues);
cancel and cash-out families run their own sub-rules because they need prior
session state (cumulative percentages, placement currency).

Rules deliberately excluded (not locally verifiable): line-service odds
(-401..-433), risk/liability (-5xx/-7xx), bookmaker min/max stake (-306/-308),
currency-enabled-in-MTS (-312), tournament-correlation contingencies
(-320/-323/-328) which need feed data, and the extended-ways combination cap
(-334) whose generation algorithm is not published.
"""

from __future__ import annotations

import time
from typing import Any

from mts_client_integration.models.business_rules import BusinessRuleIssue, PriorState
from mts_client_integration.services.business_rules.bet_structure import (
    check_bet_ids_all_or_none,
    check_bet_types,
    check_non_sr_and_bankers,
    check_odds_change,
)
from mts_client_integration.services.business_rules.cancel import check_cancel
from mts_client_integration.services.business_rules.cashout import check_cashout
from mts_client_integration.services.business_rules.custom_bet import check_custom_bets
from mts_client_integration.services.business_rules.envelope import (
    check_frame_size,
    check_timestamp,
)
from mts_client_integration.services.business_rules.inputs import (
    EnvelopeRule,
    EnvelopeRuleInput,
    TicketRule,
    TicketRuleInput,
)
from mts_client_integration.services.business_rules.selections import (
    check_duplicate_selections,
    check_leaf_rules,
    check_selection_cap,
)
from mts_client_integration.services.business_rules.stakes import check_multibet
from mts_client_integration.services.business_rules.ticket_context import (
    check_context,
    check_inform_bet_validations,
)
from mts_client_integration.services.ticket_tree import (
    as_dict,
    as_str,
    extract_cancel,
    extract_cashout,
    extract_ticket,
)

ENVELOPE_RULES: tuple[EnvelopeRule, ...] = (check_timestamp, check_frame_size)

TICKET_RULES: tuple[TicketRule, ...] = (
    check_selection_cap,
    check_bet_ids_all_or_none,
    check_leaf_rules,
    check_duplicate_selections,
    check_bet_types,
    check_non_sr_and_bankers,
    check_custom_bets,
    check_odds_change,
    check_context,
    check_multibet,
    check_inform_bet_validations,
)


def evaluate_business_rules(
    payload: dict[str, Any],
    *,
    operation: str | None = None,
    reference_time_utc_ms: int | None = None,
    serialized_bytes: int | None = None,
    prior_state: PriorState | None = None,
) -> list[BusinessRuleIssue]:
    """Run all applicable business rules against a raw request payload."""
    content = as_dict(payload.get("content")) or {}
    resolved_operation = operation or as_str(payload.get("operation"))
    reference = int(time.time() * 1000) if reference_time_utc_ms is None else reference_time_utc_ms
    state = prior_state or PriorState()

    envelope = EnvelopeRuleInput(payload, reference, serialized_bytes)
    issues = [issue for rule in ENVELOPE_RULES for issue in rule(envelope)]

    ticket = extract_ticket(content)
    if ticket is not None:
        ticket_input = TicketRuleInput(ticket, content, resolved_operation)
        issues.extend(issue for rule in TICKET_RULES for issue in rule(ticket_input))

    cancel = extract_cancel(content)
    if cancel is not None:
        issues.extend(check_cancel(cancel, state))

    cashout = extract_cashout(content)
    if cashout is not None:
        issues.extend(check_cashout(cashout, state))

    return issues
