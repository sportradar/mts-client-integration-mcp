"""Dataclasses and schemas for rejection code lookup."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from mts_client_integration.models.ticket3.operations import OPERATION_TO_CONTENT_TYPE

_TICKET_OPERATIONS_DOC = ", ".join(op.value for op in OPERATION_TO_CONTENT_TYPE)


@dataclass(frozen=True)
class RejectionVariant:
    message: str
    category: str | None = None
    operations: tuple[str, ...] = ()


@dataclass(frozen=True)
class RejectionCodeRecord:
    code: int
    variants: tuple[RejectionVariant, ...]
    steps_to_reproduce: tuple[str, ...] = ()
    fix_suggestions: tuple[str, ...] = ()


class TicketContext(BaseModel):
    """Minimal context from the rejected MTS request.

    Agents should copy fields from the Ticket 3.0 request envelope that was
    rejected. Only documented fields are used; additional keys are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    operation: str | None = Field(
        default=None,
        description=(
            "The `operation` field from the Ticket 3.0 request JSON sent to MTS "
            "(top-level key, same name). Required when the rejection code is shared "
            "across operations. Valid values: "
            f"{_TICKET_OPERATIONS_DOC}."
        ),
        examples=["ticket-placement", "cashout-build"],
    )


def resolve_operation(
    *,
    operation: str | None = None,
    ticket_context: TicketContext | None = None,
) -> str | None:
    """Resolve the MTS operation used to disambiguate rejection codes."""
    if operation is not None:
        return operation
    if ticket_context is not None and ticket_context.operation is not None:
        return ticket_context.operation
    return None


@dataclass(frozen=True)
class RejectionLookupResult:
    code: int
    message: str | None
    found: bool
    operations: tuple[str, ...] = ()
    category: str | None = None
    ambiguous: bool = False
    steps_to_reproduce: tuple[str, ...] = ()
    fix_suggestions: tuple[str, ...] = ()

    def to_response_dict(self) -> dict[str, object]:
        """Serialize for MCP tool output; omit optional guidance when empty."""
        response: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "found": self.found,
            "operations": list(self.operations),
            "category": self.category,
            "ambiguous": self.ambiguous,
        }
        if self.steps_to_reproduce:
            response["steps_to_reproduce"] = list(self.steps_to_reproduce)
        if self.fix_suggestions:
            response["fix_suggestions"] = list(self.fix_suggestions)
        return response
