# 05 — Partial cash-out sent as an increment (the classic bug)

**Goal:** The cumulative-percentage rule. The bet was already cashed out 50%
(`0.5`). The operator now wants "another 30%" and incorrectly sends
`percentage: "0.3"` — the increment — instead of the cumulative `0.8`. Because
partial cash-out `percentage` is the **cumulative fraction of the original
stake**, `0.3` is lower than the previous `0.5` and MTS rejects it (`-211`).

The prior placement and first cash-out are described in the prompt so the
validator can reconstruct session state.

**Expected result:**
- `schema_ok: true`, `envelope_ok: true`
- `business_rules_ok: false`
- `business_rules` includes:
  - `cashout_percentage_monotonic` → `severity: error`, `maps_to_code: -211`
    (`0.3` is lower than the previous `0.5`)
  - `cashout_cumulative_percentage` → `severity: warning`, `maps_to_code: -211`
    (reminder that the value must be cumulative, not incremental)

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

The customer now wants to cash out another 30%, so I'm about to send
`percentage: "0.3"`. Is that correct?

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
      "percentage": "0.3",
      "payout": [{"type": "cash", "currency": "EUR", "amount": "3"}]
    }
  },
  "correlationId": "cash-corr-2",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cashout",
  "version": "3.0"
}
```
