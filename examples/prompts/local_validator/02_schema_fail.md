# 02 — ticket-placement missing a required field (schema fails)

**Goal:** The same ticket as #01 but with the required `context.limitId`
removed. JSON Schema validation should fail.

**Expected result:**
- `schema_ok: false`
- `schema_errors` contains an entry whose `path` points at `$.content.context`
  with a message like `'limitId' is a required property` (`rule_id: jsonschema`).
- `envelope_ok` may also be `false` (the typed envelope requires `limitId` too).

---

## Prompt

I'm about to send this ticket-placement to MTS. Can you validate it and tell me
why MTS would reject it?

```json
{
  "operatorId": "9985",
  "content": {
    "type": "ticket",
    "ticketId": "1000000001",
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
        "stake": [{"type": "cash", "currency": "EUR", "amount": "10"}]
      }
    ],
    "context": {
      "channel": {"type": "internet", "ip": "127.0.0.1", "lang": "en"},
      "endCustomer": {"id": "user3454"}
    }
  },
  "correlationId": "CRL0000001",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```
