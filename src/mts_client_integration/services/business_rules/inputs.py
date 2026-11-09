"""Shared input types for business rules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mts_client_integration.models.business_rules import BusinessRuleIssue
from mts_client_integration.services.ticket_tree import as_list


@dataclass(frozen=True)
class TicketRuleInput:
    """What a ticket-level rule inspects: the ticket object plus its surrounding content."""

    ticket: dict[str, Any]
    content: dict[str, Any]
    operation: str | None

    @property
    def bets(self) -> list[Any]:
        return as_list(self.ticket.get("bets"))


@dataclass(frozen=True)
class EnvelopeRuleInput:
    """What an envelope-level rule inspects."""

    payload: dict[str, Any]
    reference_time_utc_ms: int
    serialized_bytes: int | None


TicketRule = Callable[[TicketRuleInput], list[BusinessRuleIssue]]
EnvelopeRule = Callable[[EnvelopeRuleInput], list[BusinessRuleIssue]]
