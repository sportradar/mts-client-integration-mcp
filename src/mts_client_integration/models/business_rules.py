"""Dataclasses and reference tables for business-rule and ACK validation.

These types back MVP capability #2 (local validator): the business-rule layer
and the ACK / nACK state machine described in ``mts-mcp-server-mvp.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

Severity = Literal["error", "warning", "info"]

# Minimum decimal odds MTS accepts on a selection (-316).
MIN_DECIMAL_ODDS = Decimal("1.01")

# WebSocket framing limits: messages are split into frames of at most 32 KB, and
# at most 4 frames (128 KB) per message; MTS closes the connection with 1009 above that.
MAX_FRAME_BYTES = 32 * 1024
MAX_FRAMES = 4
MAX_MESSAGE_BYTES = MAX_FRAME_BYTES * MAX_FRAMES


@dataclass(frozen=True)
class BusinessRuleIssue:
    """A single business-rule finding on an outbound Ticket 3.0 request."""

    rule_id: str
    severity: Severity
    path: str
    message: str
    maps_to_code: int | None = None


@dataclass(frozen=True)
class AckIssue:
    """A single ACK / nACK state-machine finding derived from the session state."""

    rule_id: str
    severity: Severity
    message: str
    correlation_id: str | None = None
    ticket_id: str | None = None


@dataclass(frozen=True)
class SessionStateError:
    """A message that could not be parsed or paired within the session state."""

    message: str
    index: int | None = None


@dataclass(frozen=True)
class SessionStateEntry:
    """A single parsed wire message with its resolved direction."""

    direction: Literal["outbound", "inbound"]
    message: dict[str, object]
    index: int
    operation: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True)
class SessionStateParseResult:
    """Outcome of parsing a session_state input into typed entries."""

    entries: tuple[SessionStateEntry, ...] = ()
    errors: tuple[SessionStateError, ...] = field(default_factory=tuple)


@dataclass
class PriorState:
    """Context derived from earlier session messages, used by stateful rules.

    Keyed by ticket id. Percentages are the cumulative fractions already sent.
    """

    cashout_percentages: dict[str, list[Decimal]] = field(default_factory=dict)
    cancel_percentages: dict[str, list[Decimal]] = field(default_factory=dict)
    placement_currencies: dict[str, set[str]] = field(default_factory=dict)

    def previous_cashout_percentages(self, ticket_id: str | None) -> list[Decimal]:
        return self.cashout_percentages.get(ticket_id, []) if ticket_id else []

    def previous_cancel_percentages(self, ticket_id: str | None) -> list[Decimal]:
        return self.cancel_percentages.get(ticket_id, []) if ticket_id else []

    def currencies_placed_for(self, ticket_id: str | None) -> set[str]:
        return self.placement_currencies.get(ticket_id, set()) if ticket_id else set()


# Predefined system permutations. Keyed by the
# sorted ``size`` array; value is the human-facing bet name.
PREDEFINED_SYSTEM_SIZES: dict[tuple[int, ...], str] = {
    (2, 3): "Trixie",
    (2, 3, 4): "Yankee",
    (2, 3, 4, 5): "Super Yankee / Canadian",
    (2, 3, 4, 5, 6): "Heinz",
    (2, 3, 4, 5, 6, 7): "Super Heinz",
    (2, 3, 4, 5, 6, 7, 8): "Goliath",
    (1, 2, 3): "Patent",
    (1, 2, 3, 4): "Lucky 15",
    (1, 2, 3, 4, 5): "Lucky 31",
    (1, 2, 3, 4, 5, 6): "Lucky 63",
}

# Cancellation codes exercised in client integration certification.
CANCEL_CODES_ACK_REQUIRED: frozenset[int] = frozenset({101, 103, 104, 105})
CANCEL_CODES_NO_ACK: frozenset[int] = frozenset({301, 302})
CANCEL_CODES_ALLOWED: frozenset[int] = CANCEL_CODES_ACK_REQUIRED | CANCEL_CODES_NO_ACK
# Partial cancellation is only available for codes 101 and 103.
PARTIAL_CANCEL_CODES: frozenset[int] = frozenset({101, 103})

# Classic UOF + C-Odds producers.
KNOWN_PRODUCER_IDS: frozenset[str] = frozenset({"1", "3", "4", "5", "14"})

# Variant goal scorer markets MTS does not support.
UNSUPPORTED_MARKET_IDS: frozenset[str] = frozenset({"892", "893"})


# Mandatory-field matrix per channel type for certification ticket format checks.
# Schema is more permissive; these are CI expectations surfaced as warnings.
# ``needs_end_customer`` is treated as a soft (warning) expectation because
# unregistered retail/terminal legitimately omit it.
@dataclass(frozen=True)
class ChannelExpectation:
    required_fields: frozenset[str]
    needs_end_customer: bool


CHANNEL_CI_EXPECTATIONS: dict[str, ChannelExpectation] = {
    "internet": ChannelExpectation(frozenset({"ip", "lang"}), True),
    "mobile": ChannelExpectation(frozenset({"ip", "lang"}), True),
    "mobile-app": ChannelExpectation(frozenset({"ip", "lang"}), True),
    "tv-app": ChannelExpectation(frozenset({"ip", "lang"}), True),
    "agent": ChannelExpectation(frozenset({"lang"}), True),
    "call-centre": ChannelExpectation(frozenset({"lang"}), True),
    "phone": ChannelExpectation(frozenset({"lang"}), True),
    "sms": ChannelExpectation(frozenset({"lang"}), True),
    "retail": ChannelExpectation(frozenset({"shopId", "lang"}), False),
    "terminal": ChannelExpectation(frozenset({"shopId", "terminalId", "lang"}), True),
}

# ISO 639-1 two-letter language codes (schema lang is ISO 639-1, maxLength 2).
ISO_639_1_CODES: frozenset[str] = frozenset(
    {
        "aa",
        "ab",
        "ae",
        "af",
        "ak",
        "am",
        "an",
        "ar",
        "as",
        "av",
        "ay",
        "az",
        "ba",
        "be",
        "bg",
        "bh",
        "bi",
        "bm",
        "bn",
        "bo",
        "br",
        "bs",
        "ca",
        "ce",
        "ch",
        "co",
        "cr",
        "cs",
        "cu",
        "cv",
        "cy",
        "da",
        "de",
        "dv",
        "dz",
        "ee",
        "el",
        "en",
        "eo",
        "es",
        "et",
        "eu",
        "fa",
        "ff",
        "fi",
        "fj",
        "fo",
        "fr",
        "fy",
        "ga",
        "gd",
        "gl",
        "gn",
        "gu",
        "gv",
        "ha",
        "he",
        "hi",
        "ho",
        "hr",
        "ht",
        "hu",
        "hy",
        "hz",
        "ia",
        "id",
        "ie",
        "ig",
        "ii",
        "ik",
        "io",
        "is",
        "it",
        "iu",
        "ja",
        "jv",
        "ka",
        "kg",
        "ki",
        "kj",
        "kk",
        "kl",
        "km",
        "kn",
        "ko",
        "kr",
        "ks",
        "ku",
        "kv",
        "kw",
        "ky",
        "la",
        "lb",
        "lg",
        "li",
        "ln",
        "lo",
        "lt",
        "lu",
        "lv",
        "mg",
        "mh",
        "mi",
        "mk",
        "ml",
        "mn",
        "mr",
        "ms",
        "mt",
        "my",
        "na",
        "nb",
        "nd",
        "ne",
        "ng",
        "nl",
        "nn",
        "no",
        "nr",
        "nv",
        "ny",
        "oc",
        "oj",
        "om",
        "or",
        "os",
        "pa",
        "pi",
        "pl",
        "ps",
        "pt",
        "qu",
        "rm",
        "rn",
        "ro",
        "ru",
        "rw",
        "sa",
        "sc",
        "sd",
        "se",
        "sg",
        "si",
        "sk",
        "sl",
        "sm",
        "sn",
        "so",
        "sq",
        "sr",
        "ss",
        "st",
        "su",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "ti",
        "tk",
        "tl",
        "tn",
        "to",
        "tr",
        "ts",
        "tt",
        "tw",
        "ty",
        "ug",
        "uk",
        "ur",
        "uz",
        "ve",
        "vi",
        "vo",
        "wa",
        "wo",
        "xh",
        "yi",
        "yo",
        "za",
        "zh",
        "zu",
    }
)
