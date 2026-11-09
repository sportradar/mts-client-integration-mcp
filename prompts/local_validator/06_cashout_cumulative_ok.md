# 06 — Partial cash-out sent cumulatively (correct)

**Goal:** Same situation as #05, but done correctly. After a 50% cash-out, the
next partial cash-out is expressed as the cumulative `0.8` (50% + a further 30%
of the original stake). This passes the monotonicity check.

**Expected result:**
- `schema_ok: true`, `envelope_ok: true`
- No `cashout_percentage_monotonic` error (`0.8` ≥ `0.5`).
- `cashout_cumulative_percentage` → `severity: warning` is still emitted as a
  reminder because a prior cash-out exists on this ticket; it is advisory and
  does **not** flip `business_rules_ok`.
- `business_rules_ok: true` (no `error`-severity business rules).

---

## Prompt

I placed this ticket to MTS:

```json
{
  "operatorId": "9985",
  "content": {
    "type": "ticket",
    "ticketId": "2337926713",
    "bets": [
      {
        "selections": [
          {"type": "uf", "productId": "3", "eventId": "sr:match:15050881", "marketId": "1", "outcomeId": "2", "odds": {"type": "decimal", "value": "1.32"}}
        ],
        "stake": [{"type": "cash", "currency": "EUR", "amount": "10"}]
      }
    ],
    "context": {
      "channel": {"type": "internet", "ip": "212.7.5.2", "lang": "en"},
      "endCustomer": {"id": "user3454"},
      "limitId": 1409
    }
  },
  "correlationId": "place-corr-1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```

MTS accepted the ticket. Then I cashed out 50% with:

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cashout",
    "cashoutId": "co-1",
    "details": {
      "type": "ticket-partial",
      "ticketId": "2337926713",
      "ticketSignature": "sigAbc",
      "code": 0,
      "percentage": "0.5",
      "payout": [{"type": "cash", "currency": "EUR", "amount": "5"}]
    }
  },
  "correlationId": "cash-corr-1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cashout",
  "version": "3.0"
}
```

The customer wants a further 30% of the original stake cashed out, so I'm sending
the cumulative `percentage: "0.8"`. Can you validate that?

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cashout",
    "cashoutId": "co-2",
    "details": {
      "type": "ticket-partial",
      "ticketId": "2337926713",
      "ticketSignature": "sigAbc",
      "code": 0,
      "percentage": "0.8",
      "payout": [{"type": "cash", "currency": "EUR", "amount": "3"}]
    }
  },
  "correlationId": "cash-corr-2",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cashout",
  "version": "3.0"
}
```
