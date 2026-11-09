"""Polymorphic Ticket 3.0 request content models."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ._generated import (
    AccountDetailsInform,
    AccountInterventionInform,
    AccountLimitInform,
    AccountLimitReachedInform,
    AccountStatusInform,
    AutoCashout,
    AutoCashoutCancel,
    BalanceChangeInform,
    CampaignOptin,
    CampaignOptout,
    Cancel,
    CancelAck,
    Cashout,
    CashoutAck,
    CashoutBuild,
    CashoutBuildSubscription,
    CashoutInform,
    CashoutInformAck,
    CashoutPlacement,
    CashoutPlacementAck,
    CasinoSessionsInform,
    DepositInform,
    ExtSettlement,
    ExtSettlementAck,
    LoginInform,
    ManualReview,
    MaxStake,
    PayoutModifierSettlement,
    RegistrationInform,
    Ticket,
    TicketAck,
    TicketBuild,
    TicketInform,
    WithdrawalInform,
)

ReqContent = Annotated[
    Ticket
    | TicketAck
    | Cancel
    | CancelAck
    | Cashout
    | CashoutAck
    | ExtSettlement
    | ExtSettlementAck
    | TicketInform
    | TicketBuild
    | CasinoSessionsInform
    | BalanceChangeInform
    | DepositInform
    | WithdrawalInform
    | CashoutInform
    | CashoutBuild
    | CashoutPlacement
    | MaxStake
    | AccountLimitInform
    | AccountLimitReachedInform
    | AccountStatusInform
    | AccountInterventionInform
    | PayoutModifierSettlement
    | AutoCashout
    | AutoCashoutCancel
    | CampaignOptin
    | CampaignOptout
    | AccountDetailsInform
    | RegistrationInform
    | LoginInform
    | CashoutInformAck
    | CashoutPlacementAck
    | ManualReview
    | CashoutBuildSubscription,
    Field(discriminator="type"),
]
