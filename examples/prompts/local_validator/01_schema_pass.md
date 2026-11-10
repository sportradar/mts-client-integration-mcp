# 01 — Valid ticket-placement (schema passes)

**Goal:** A well-formed single-selection ticket-placement should pass every
layer: schema, envelope, business rules, and (with no prior exchange) the ACK
machine.

**Expected result:**
- `schema_ok: true`
- `envelope_ok: true`
- `business_rules_ok: true`
- `ack_state_machine_ok: true`
- Empty `business_rules`, `ack_state_machine`, and `session_state_errors`.

---

## Prompt

I'm about to send this ticket-placement to MTS. Can you validate it?

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
      "endCustomer": {"id": "user3454"},
      "limitId": 1409
    }
  },
  "correlationId": "CRL0000001",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```
