# 03 — Business rules the schema does not catch (stake & currency)

**Goal:** A ticket that is schema-valid but violates business rules the JSON
Schema alone does not enforce: a **zero stake** (schema allows `>= 0`) and a
**malformed currency** (schema only checks length, so `"EURO"` slips through).

> Minimum-odds (`min_odds_1_01`, `-316`) is also a business rule, but decimal
> odds below `1.01` are already rejected by the schema's odds pattern, so it
> cannot be demonstrated on an otherwise schema-valid ticket.

**Expected result:**
- `schema_ok: true`, `envelope_ok: true`
- `business_rules_ok: false`
- `business_rules` includes (both `severity: error`):
  - `positive_stake` → `maps_to_code: -301` (stake amount `0`)
  - `currency_format` → `maps_to_code: -307` (`"EURO"` is not a 3-letter code)

---

## Prompt

This ticket passes JSON schema but I think the stake and currency are wrong.
Can you check the business rules before I send it to MTS?

```json
{
  "operatorId": "9985",
  "content": {
    "type": "ticket",
    "ticketId": "1000000002",
    "bets": [
      {
        "selections": [
          {
            "type": "uf",
            "productId": "3",
            "eventId": "sr:match:10000001",
            "marketId": "1",
            "outcomeId": "2",
            "odds": {"type": "decimal", "value": "1.32"}
          }
        ],
        "stake": [{"type": "cash", "currency": "EURO", "amount": "0"}]
      }
    ],
    "context": {
      "channel": {"type": "internet", "ip": "127.0.0.1", "lang": "en"},
      "endCustomer": {"id": "user3454"},
      "limitId": 1409
    }
  },
  "correlationId": "CRL0000002",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```
