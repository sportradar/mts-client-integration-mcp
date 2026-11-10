# 14 — Accepted ticket, nACK signals a failed booking

**Goal:** MTS accepted the ticket, but the client could not book it locally and
sends a **nACK** — a `ticket-ack` with `acknowledged: false`. This is a valid
(intentional) message that tells MTS to treat the ticket as not placed; the
validator surfaces it as an informational note.

**Expected result:**
- `ack_state_machine` includes `ticket_nack_failed_booking` (`severity: info`).
- `ack_state_machine_ok: true` (info does not flip the flag).

---

## Prompt

I sent this ticket-placement to MTS:

```json
{
  "operatorId": "9985",
  "content": {
    "type": "ticket",
    "ticketId": "1000000001",
    "bets": [
      {
        "selections": [
          {"type": "uf", "productId": "3", "eventId": "sr:match:10000001", "marketId": "1", "outcomeId": "2", "odds": {"type": "decimal", "value": "1.32"}}
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
  "correlationId": "place-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```

MTS accepted it and replied with:

```json
{
  "content": {"type": "ticket-reply", "ticketId": "1000000001", "status": "accepted", "code": 0, "signature": "tsig1"},
  "correlationId": "place-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```

My system failed to book the ticket locally, so I'm sending a nACK
(`acknowledged: false`). Is this correct?

```json
{
  "operatorId": "9985",
  "content": {
    "type": "ticket-ack",
    "ticketId": "1000000001",
    "ticketSignature": "tsig1",
    "acknowledged": false
  },
  "correlationId": "place-ack-1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement-ack",
  "version": "3.0"
}
```
