# Local Validator — Test Prompts

Copy-paste prompts for exercising the `validate_ticket_request` MCP tool (MVP capability
#2). Each file is a self-contained scenario: a **Goal**, a human-like **Prompt**
(the kind of message an integrator would paste into chat), and the **expected
result**.

Prompts that involve prior traffic describe the exchange in plain language
(“I sent …”, “MTS accepted …”) with embedded JSON envelopes, rather than a
structured `session_state` array.

> **Note on timestamps:** example envelopes use a fixed, historical
> `timestampUtc` (`1745311871018`). Without pinning the validator clock, you
> may also see a `timestamp_not_stale` (`-310`) advisory on those samples.

## Index

| # | File | Exercises |
|---|------|-----------|
| 01 | `01_schema_pass.md` | Valid ticket-placement → all layers green |
| 02 | `02_schema_fail.md` | Missing required field → `schema_ok: false` |
| 03 | `03_business_rules_stake_odds_currency.md` | Positive stake, min odds, currency format |
| 04 | `04_business_rules_system_ways.md` | Predefined system, ways same-event, non-SR-in-system |
| 05 | `05_cashout_cumulative_bug.md` | Partial cash-out sent as increment (`0.5` → `0.3`) |
| 06 | `06_cashout_cumulative_ok.md` | Partial cash-out sent cumulatively (`0.5` → `0.8`) |
| 07 | `07_cancel_ack_required_accepted_103.md` | Accepted cancel 103, ACK missing |
| 08 | `08_cancel_ack_ok_accepted_103.md` | Accepted cancel 103, ACK present |
| 09 | `09_cancel_no_ack_accepted_301.md` | Accepted cancel 301, ACK must NOT be sent |
| 10 | `10_cancel_nack_on_rejected.md` | Rejected cancel requires nACK |
| 11 | `11_cancel_ack_signature_mismatch.md` | ACK signature ≠ response signature |
| 12 | `12_ticket_ack_required_accepted.md` | Accepted ticket, ACK missing (info) |
| 13 | `13_ticket_ack_ok_accepted.md` | Accepted ticket, ACK present |
| 14 | `14_ticket_nack_failed_booking.md` | Accepted ticket, nACK signals failed booking |
| 15 | `15_ticket_ack_on_rejected_warning.md` | Rejected ticket should not be ACKed |

## Response reminder

`validate_ticket_request` returns `schema_ok`, `envelope_ok`, `business_rules_ok`,
`ack_state_machine_ok` booleans plus `business_rules[]`, `ack_state_machine[]`,
and `session_state_errors[]`. Only `error`-severity findings flip a `*_ok` flag;
`warning`/`info` findings are advisory.
