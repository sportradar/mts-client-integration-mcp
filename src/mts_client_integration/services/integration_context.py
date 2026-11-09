"""Envelope context documentation for builder tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperatorLimitExample:
    operator_id: str
    limit_id: int
    notes: str


# Example pairs for documentation only; never used as defaults.
EXAMPLE_OPERATOR_LIMIT_PAIRS: tuple[OperatorLimitExample, ...] = (
    OperatorLimitExample("9985", 1409, "Common E2E integration profile"),
    OperatorLimitExample("22017", 1479, "Alternate E2E profile"),
    OperatorLimitExample("22107", 1000, "Another E2E profile"),
)


def _operator_limit_table() -> str:
    rows = [
        f"| {pair.operator_id} | {pair.limit_id} | {pair.notes} |"
        for pair in EXAMPLE_OPERATOR_LIMIT_PAIRS
    ]
    header = "| operatorId | limitId | Notes |\n|------------|---------|-------|\n"
    return header + "\n".join(rows) + "\n"


_ENVELOPE_CONTEXT_TEMPLATE = """\
# Ticket 3.0 envelope context — integration fields

The builder tools (**build_placement**, **build_cashout**, **build_ext_settlement**) require
every business field explicitly. Copy values from your integration profile and odds feed;
do not guess.

## Fields that matter for MTS traffic

| Param | Wire field | How to obtain it |
|-------|------------|------------------|
| ``operator_id`` | ``operatorId`` | Your MTS integration profile |
| ``limit_id`` | ``content.context.limitId`` | Configured limit for your operator in MTS |
| ``channel`` | ``content.context.channel`` | Per ``type`` in JSON Schema. |
| | | Internet/mobile: ``ip``, ``lang``. Retail: ``shopId``. |
| | | Terminal: ``shopId``, ``terminalId``. |
| ``end_customer_id`` | ``content.context.endCustomer.id`` | Optional. Omit → no ``endCustomer``. |

Placement tickets require ``operator_id``, ``limit_id``, ``channel``, ``stake``, and ``currency``.
Cashout and ext-settlement require ``operator_id`` and ``currency``.

## Example operator/limit pairs from E2E (not prescriptive)

These appear in **documentation and preset examples**; use the pair your operator
registered with MTS:

{operator_limit_table}
## Workflow

1. Call ``list_ticket_shapes()`` and read ``mts://templates/{shape}`` (tool name,
   required fields, schema fragment, example).
2. Fill required params from the integrator (never guess operator id, limit id,
   odds, or cashout percentage).
3. Call the matching build tool with typed params.
4. Run ``validate_ticket_request`` on ``payload`` for schema and business rules.
"""


ENVELOPE_CONTEXT_DOC = _ENVELOPE_CONTEXT_TEMPLATE.replace(
    "{operator_limit_table}", _operator_limit_table()
)


def get_envelope_context_documentation() -> dict[str, object]:
    """Structured companion to ``ENVELOPE_CONTEXT_DOC`` for MCP resources."""
    return {
        "builder_tools": {
            "placement": "build_placement",
            "cashout": "build_cashout",
            "ext_settlement": "build_ext_settlement",
        },
        "example_operator_limit_pairs": [
            {"operator_id": pair.operator_id, "limit_id": pair.limit_id, "notes": pair.notes}
            for pair in EXAMPLE_OPERATOR_LIMIT_PAIRS
        ],
        "rejection_codes": {
            "missing_limit_id": -209,
            "limit_not_found": -509,
        },
    }
