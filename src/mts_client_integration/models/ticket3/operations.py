"""Maps Ticket 3.0 request operations to expected content.type values."""

from __future__ import annotations

from ._generated import Operation

OPERATION_TO_CONTENT_TYPE: dict[Operation, str] = {
    Operation.ticket_placement: "ticket",
    Operation.ticket_cancel: "cancel",
    Operation.ticket_cashout: "cashout",
    Operation.ticket_ext_settlement: "ext-settlement",
    Operation.ticket_placement_ack: "ticket-ack",
    Operation.ticket_cancel_ack: "cancel-ack",
    Operation.ticket_cashout_ack: "cashout-ack",
    Operation.ticket_ext_settlement_ack: "ext-settlement-ack",
    Operation.ticket_placement_inform: "ticket-inform",
    Operation.ticket_build: "ticket-build",
    Operation.casino_sessions_inform: "casino-sessions-inform",
    Operation.balance_change_inform: "balance-change-inform",
    Operation.balance_deposit_inform: "deposit-inform",
    Operation.balance_withdrawal_inform: "withdrawal-inform",
    Operation.cashout_inform: "cashout-inform",
    Operation.cashout_build: "cashout-build",
    Operation.cashout_placement: "cashout-placement",
    Operation.max_stake: "max-stake",
    Operation.account_limit_inform: "account-limit-inform",
    Operation.account_limit_reached_inform: "account-limit-reached-inform",
    Operation.account_status_inform: "account-status-inform",
    Operation.account_intervention_inform: "account-intervention-inform",
    Operation.payout_modifier_settlement: "payout-modifier-settlement",
    Operation.auto_cashout: "auto-cashout",
    Operation.auto_cashout_cancel: "auto-cashout-cancel",
    Operation.campaign_optin: "campaign-optin",
    Operation.campaign_optout: "campaign-optout",
    Operation.account_details_inform: "account-details-inform",
    Operation.registration_inform: "registration-inform",
    Operation.login_inform: "login-inform",
    Operation.cashout_inform_ack: "cashout-inform-ack",
    Operation.cashout_placement_ack: "cashout-placement-ack",
    Operation.manual_review: "manual-review",
    Operation.cashout_build_subscription: "cashout-build-subscription",
}
