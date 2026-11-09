"""Models for the golden-ticket builder (MVP capability #3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from mts_client_integration.models.business_rules import MIN_DECIMAL_ODDS

BetType = Literal["single", "accumulator", "system", "ways", "custom_bet"]
BuilderKind = Literal["placement", "cashout", "ext_settlement"]
ChannelType = Literal[
    "internet",
    "mobile",
    "mobile-app",
    "tv-app",
    "agent",
    "call-centre",
    "phone",
    "sms",
    "retail",
    "terminal",
]
PresetStatus = Literal["available", "planned"]
SettlementLevel = Literal["bet", "ticket"]

# ISO 4217 alpha-3 or mBTC (MTS business rules), accepted in any case and
# normalized by ``_normalize_currency`` (the wire format is upper-case / ``mBTC``).
_CURRENCY_RE = re.compile(r"^([A-Za-z]{3}|[Mm][Bb][Tt][Cc])$")
# End-customer id per Ticket 3.0 schema
_END_CUSTOMER_ID_RE = re.compile(r"^[0-9A-Za-z#\-_]{1,36}$")
# Unsigned decimal string (stake, payout, odds). Positivity is checked separately
# because the pydantic regex engine has no look-around support.
_DECIMAL_RE = re.compile(r"^\d+(\.\d+)?$")
_LANG_RE = re.compile(r"^[a-z]{2}$")


def _ensure_positive_decimal(value: str) -> str:
    """Reject ``"0"`` / ``"0.00"``: the regex alone only guarantees decimal format."""
    if Decimal(value) <= 0:
        msg = f"amount must be greater than 0, got {value!r}"
        raise ValueError(msg)
    return value


def _normalize_currency(value: object) -> object:
    """Normalize case: ``eur`` -> ``EUR``, ``mbtc`` -> ``mBTC``. Non-strings pass through."""
    if not isinstance(value, str):
        return value
    return "mBTC" if value.lower() == "mbtc" else value.upper()


CurrencyStr = Annotated[
    str,
    BeforeValidator(_normalize_currency),
    StringConstraints(pattern=_CURRENCY_RE.pattern),
]

PositiveDecimalStr = Annotated[
    str,
    StringConstraints(pattern=_DECIMAL_RE.pattern),
    AfterValidator(_ensure_positive_decimal),
]


class SelectionParams(BaseModel):
    """One bet selection (Sportradar UOF or external/non-SR)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["uf", "external"] = "uf"
    event_id: str | None = Field(
        default=None,
        description="UOF event id (sr:match:…). Required for uf selections.",
    )
    market_id: str | None = Field(
        default=None,
        description="UOF market id from the odds feed (uf only).",
    )
    outcome_id: str | None = Field(
        default=None,
        description="UOF outcome id from the odds feed (uf only).",
    )
    odds: str = Field(
        ...,
        description=(
            "Decimal odds as a string from your feed, at least 1.01. "
            "Do not invent — use the value MTS will accept for this outcome."
        ),
        pattern=_DECIMAL_RE.pattern,
    )
    product_id: str | None = Field(
        default=None,
        description="UOF producer id: 1 = live, 3 = prematch (uf only).",
        pattern=r"^[0-9]+$",
    )
    specifiers: str | None = None
    event: str | None = Field(
        default=None,
        description="External event key (e.g. ext:match:…). Required for external selections.",
    )
    outcome: str | None = Field(
        default=None,
        description="External outcome key. Required for external selections.",
    )
    exp_settle_time: int | None = Field(
        default=None,
        description="Unix ms settlement time for external selections.",
        ge=0,
    )

    @staticmethod
    def _odds_decimal(value: str) -> Decimal:
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            msg = f"invalid decimal odds: {value!r}"
            raise ValueError(msg) from exc

    @model_validator(mode="after")
    def selection_fields_match_type(self) -> SelectionParams:
        if self.type == "uf":
            if not self.event_id:
                msg = "uf selections require event_id"
                raise ValueError(msg)
            for field_name in ("market_id", "outcome_id", "product_id"):
                if getattr(self, field_name) is None:
                    msg = f"uf selections require {field_name}"
                    raise ValueError(msg)
            odds_val = self._odds_decimal(self.odds)
            if odds_val < MIN_DECIMAL_ODDS:
                msg = f"odds must be at least {MIN_DECIMAL_ODDS}, got {odds_val}"
                raise ValueError(msg)
            return self
        if self.type == "external":
            if not self.event or not self.outcome or self.exp_settle_time is None:
                msg = "external selections require event, outcome, and exp_settle_time"
                raise ValueError(msg)
            odds_val = self._odds_decimal(self.odds)
            if odds_val < MIN_DECIMAL_ODDS:
                msg = f"odds must be at least {MIN_DECIMAL_ODDS}, got {odds_val}"
                raise ValueError(msg)
        return self


class ChannelParams(BaseModel):
    """Distribution channel. Requirements depend on ``type`` (see Ticket 3.0 schema)."""

    model_config = ConfigDict(extra="forbid")

    type: ChannelType = Field(..., description="Channel kind (internet, retail, terminal, …).")
    lang: str = Field(
        ...,
        description="ISO 639-1 two-letter language code (lowercase), e.g. en, de.",
        pattern=_LANG_RE.pattern,
    )
    ip: str | None = Field(
        default=None,
        description="Client IP; required for internet, mobile, mobile-app, tv-app channels.",
    )
    shop_id: str | None = Field(default=None, description="Required for retail and terminal.")
    terminal_id: str | None = Field(default=None, description="Required for terminal.")
    device_id: str | None = Field(
        default=None, description="Optional device id for mobile-style channels."
    )

    @model_validator(mode="after")
    def channel_fields_for_type(self) -> ChannelParams:
        t = self.type
        needs_ip = t in {"internet", "mobile", "mobile-app", "tv-app"}
        if needs_ip and not self.ip:
            msg = f"channel type {t!r} requires ip"
            raise ValueError(msg)
        if t == "retail" and not self.shop_id:
            msg = "channel type 'retail' requires shop_id"
            raise ValueError(msg)
        if t == "terminal":
            if not self.shop_id:
                msg = "channel type 'terminal' requires shop_id"
                raise ValueError(msg)
            if not self.terminal_id:
                msg = "channel type 'terminal' requires terminal_id"
                raise ValueError(msg)
        return self


class RefParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["alt-stake", "reoffer"]
    ticket_id: str = Field(..., min_length=1)
    ticket_signature: str = Field(..., min_length=1)


class BetBuildParams(BaseModel):
    """Per-bet overrides when building a multibet ticket."""

    model_config = ConfigDict(extra="forbid")

    selections: list[SelectionParams]
    bet_type: BetType | None = None
    size: list[int] | None = None
    banker_selection_indexes: list[int] = Field(default_factory=list)
    custom_bet_odds: str | None = Field(
        default=None,
        description="Combined custom-bet odds when bet_type is custom_bet.",
        pattern=_DECIMAL_RE.pattern,
    )
    stake: PositiveDecimalStr = Field(
        ...,
        description="Cash stake amount for this bet (positive decimal string).",
    )
    currency: CurrencyStr = Field(
        ...,
        description="ISO 4217 three-letter code or mBTC (any case; normalized).",
    )

    @model_validator(mode="after")
    def custom_bet_needs_odds(self) -> BetBuildParams:
        if self.bet_type == "custom_bet" and not self.custom_bet_odds:
            msg = "custom_bet requires custom_bet_odds on each bet"
            raise ValueError(msg)
        return self


class PlacementBuildParams(BaseModel):
    """Parameters for building a ``ticket-placement`` envelope."""

    model_config = ConfigDict(extra="forbid")

    selections: list[SelectionParams] | None = None
    bets: list[BetBuildParams] | None = None
    bet_type: BetType = "single"
    size: list[int] | None = None
    banker_selection_indexes: list[int] = Field(default_factory=list)
    custom_bet_odds: str | None = Field(
        default=None,
        description="Combined odds for custom_bet (not the product of inner odds).",
        pattern=_DECIMAL_RE.pattern,
    )
    stake: PositiveDecimalStr = Field(
        ...,
        description="Cash stake amount (positive decimal string).",
    )
    currency: CurrencyStr = Field(
        ...,
        description="ISO 4217 three-letter code or mBTC (any case; normalized).",
    )
    operator_id: str = Field(
        ...,
        description="MTS operator id from your integration profile. Never invent.",
        min_length=1,
    )
    limit_id: int = Field(
        ...,
        description="Sportradar limit id configured for this operator in MTS.",
        ge=1,
    )
    channel: ChannelParams = Field(..., description="Distribution channel; fields depend on type.")
    end_customer_id: str | None = Field(
        default=None,
        description="End-user id; optional in the schema. Pattern matches MTS end-customer id.",
        pattern=_END_CUSTOMER_ID_RE.pattern,
    )
    ticket_id: str | None = None
    correlation_id: str | None = None
    timestamp_utc_ms: int | None = None
    ref: RefParams | None = None
    ways_selections: list[SelectionParams] | None = None
    outer_selections: list[SelectionParams] | None = None

    @model_validator(mode="after")
    def selections_or_bets_required(self) -> PlacementBuildParams:
        if self.bets is None and not self.selections:
            msg = "provide selections or bets"
            raise ValueError(msg)
        if self.bets is not None and self.selections:
            msg = "provide either selections or bets, not both"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def composite_params_consistent(self) -> PlacementBuildParams:
        if self.bets is not None and (self.ways_selections or self.outer_selections):
            msg = "ways_selections and outer_selections are not supported together with bets"
            raise ValueError(msg)
        if self.outer_selections and self.ways_selections is None:
            msg = "outer_selections requires ways_selections (ways_system_bankers shape)"
            raise ValueError(msg)
        if self.ways_selections is None:
            return self
        if len(self.ways_selections) < 2:
            msg = "ways_selections requires at least two same-event selections"
            raise ValueError(msg)
        if self.bet_type not in {"single", "system"}:
            msg = f"ways_selections requires bet_type 'single' or 'system', not {self.bet_type!r}"
            raise ValueError(msg)
        if self.banker_selection_indexes:
            msg = "banker_selection_indexes is not supported together with ways_selections"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def custom_bet_odds_required(self) -> PlacementBuildParams:
        if self.bet_type == "custom_bet" and not self.custom_bet_odds:
            msg = "bet_type custom_bet requires custom_bet_odds"
            raise ValueError(msg)
        return self


class CashoutBuildParams(BaseModel):
    """Parameters for building a ``ticket-cashout`` envelope."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(..., min_length=1)
    ticket_signature: str = Field(..., min_length=1)
    payout_amount: PositiveDecimalStr = Field(
        ...,
        description="Cash payout amount (positive decimal string).",
    )
    currency: CurrencyStr
    partial: bool = True
    percentage: str | None = Field(
        default=None,
        description=(
            "Cumulative fraction of original stake for partial cashout (0 < x < 1), not delta."
        ),
    )
    code: int = Field(
        ...,
        description=("Cashout code (schema: 0..1000). Ask operator docs or MTS for the value."),
        ge=0,
        le=1000,
    )
    cashout_id: str | None = None
    operator_id: str = Field(..., min_length=1, description="MTS operator id.")
    correlation_id: str | None = None
    timestamp_utc_ms: int | None = None

    @model_validator(mode="after")
    def partial_needs_percentage(self) -> CashoutBuildParams:
        if self.partial:
            if not self.percentage:
                msg = "partial cashout requires percentage"
                raise ValueError(msg)
            try:
                p = Decimal(self.percentage.strip())
            except (InvalidOperation, ValueError) as exc:
                msg = f"invalid percentage: {self.percentage!r}"
                raise ValueError(msg) from exc
            if not Decimal(0) < p < Decimal(1):
                msg = f"percentage must be in (0, 1), got {p}"
                raise ValueError(msg)
        return self


class ExtSettlementBuildParams(BaseModel):
    """Parameters for building a ``ticket-ext-settlement`` envelope."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(..., min_length=1)
    ticket_signature: str = Field(..., min_length=1)
    payout_amount: PositiveDecimalStr
    currency: CurrencyStr
    settlement_level: SettlementLevel = "bet"
    bet_id: str | None = None
    trace_id: str | None = None
    settlement_id: str | None = None
    operator_id: str = Field(..., min_length=1)
    correlation_id: str | None = None
    timestamp_utc_ms: int | None = None

    @model_validator(mode="after")
    def bet_id_required_for_bet_level(self) -> ExtSettlementBuildParams:
        if self.settlement_level == "bet" and not self.bet_id:
            msg = "bet-level ext settlement requires bet_id"
            raise ValueError(msg)
        return self


@dataclass(frozen=True)
class ShapePreset:
    """Named preset mapping an E2E bet shape to builder defaults."""

    shape: str
    description: str
    operation: str
    builder: BuilderKind
    status: PresetStatus
    defaults: dict[str, Any]
    min_selections: int | None = None
    example_params: dict[str, Any] | None = None
    required_params: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuildResult:
    """Outcome of a build tool (placement, cashout, or ext settlement)."""

    shape: str
    operation: str
    payload: dict[str, Any]

    def to_response_dict(self) -> dict[str, object]:
        return {
            "shape": self.shape,
            "operation": self.operation,
            "payload": self.payload,
        }


class PresetUnavailableError(Exception):
    """Raised when a shape preset is missing or not buildable."""

    def __init__(self, *, shape: str, message: str, available_presets: tuple[str, ...]) -> None:
        super().__init__(message)
        self.shape = shape
        self.message = message
        self.available_presets = available_presets

    def describe(self) -> str:
        """Message plus the presets the caller may use instead (for tool errors)."""
        return f"{self.message} Available presets: {', '.join(self.available_presets)}."

    def to_response_dict(self) -> dict[str, object]:
        return {
            "error": self.message,
            "shape": self.shape,
            "found": False,
            "available_presets": list(self.available_presets),
        }
