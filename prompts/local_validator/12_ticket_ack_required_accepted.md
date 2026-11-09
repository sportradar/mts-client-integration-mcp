# 12 — Accepted ticket, no acknowledgement sent

**Goal:** Ticket-placement acknowledgement flow. MTS accepted the ticket
(`ticket-reply`, `status: accepted`) but the client sent no `ticket-ack`.
Because ticket acknowledgement is config-gated (only mandatory when enabled),
this surfaces as an **info** reminder rather than an error.

**Expected result:**
- `ack_state_machine` includes `ticket_ack_on_accepted` (`severity: info`).
- `ack_state_machine_ok: true` (info does not flip the flag).

---

## Prompt

I sent this ticket-placement to MTS:

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
  "correlationId": "place-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```

MTS accepted it and replied with:

```json
{
  "content": {"type": "ticket-reply", "ticketId": "2337926713", "status": "accepted", "code": 0, "signature": "tsig1"},
  "correlationId": "place-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```

I have not sent a ticket-ack yet. Can you audit this exchange?
