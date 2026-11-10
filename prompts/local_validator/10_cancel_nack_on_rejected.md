# 10 — Rejected cancel requires a nACK

**Goal:** When MTS **rejects** a cancellation, the client must send a negative
acknowledgement — a `ticket-cancel-ack` with `acknowledged: false`. Here MTS
rejected the cancel and no nACK was sent.

**Expected result:**
- `ack_state_machine_ok: false`
- `ack_state_machine` includes `cancel_nack_on_rejected` (`severity: error`).

---

## Prompt

I sent this ticket-cancel to MTS (code 103):

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cancel",
    "cancellationId": "can-2",
    "details": {"type": "ticket", "ticketId": "1000000001", "ticketSignature": "sigT", "code": 103}
  },
  "correlationId": "cancel-x2",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel",
  "version": "3.0"
}
```

MTS rejected it and replied with:

```json
{
  "content": {"type": "cancel-reply", "cancellationId": "can-2", "ticketId": "1000000001", "status": "rejected", "code": -2001, "signature": "respSig2"},
  "correlationId": "cancel-x2",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel",
  "version": "3.0"
}
```

I did not send any acknowledgement. Can you audit this exchange?
