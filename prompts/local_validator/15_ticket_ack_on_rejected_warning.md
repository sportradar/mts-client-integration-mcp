# 15 — Rejected ticket should not be acknowledged

**Goal:** MTS **rejected** the ticket (`ticket-reply`, `status: rejected`), so
there is no placed ticket to acknowledge. Sending a `ticket-ack` for it is
pointless and is flagged as a warning.

**Expected result:**
- `ack_state_machine` includes `ticket_no_ack_on_rejected` (`severity: warning`).
- `ack_state_machine_ok: true` (warning does not flip the flag).

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

MTS rejected it and replied with:

```json
{
  "content": {"type": "ticket-reply", "ticketId": "1000000001", "status": "rejected", "code": -320, "signature": "tsig1"},
  "correlationId": "place-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```

My client still sent this ticket-ack afterward. Is that correct?

```json
{
  "operatorId": "9985",
  "content": {
    "type": "ticket-ack",
    "ticketId": "1000000001",
    "ticketSignature": "tsig1",
    "acknowledged": true
  },
  "correlationId": "place-ack-1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement-ack",
  "version": "3.0"
}
```
