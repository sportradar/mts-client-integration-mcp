# 13 — Accepted ticket, acknowledgement sent correctly

**Goal:** MTS accepted the ticket and the client sends a well-formed
`ticket-ack` (`acknowledged: true`, `ticketSignature` echoing the response
`signature`). This is the happy path.

**Expected result:**
- `ack_state_machine_ok: true`
- No `ticket_ack_on_accepted` and no `ack_matches_response_signature` findings.

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

Now I'm sending this ticket-ack. Is it correct?

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
