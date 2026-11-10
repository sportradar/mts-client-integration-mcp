# 09 — Accepted cancel (code 301), ACK must NOT be sent

**Goal:** Cancellation codes `301` and `302` are the "no acknowledgement"
branch of the matrix: once MTS accepts them, the client **must not** send an
ACK. Here the client wrongly sends a `ticket-cancel-ack`.

**Expected result:**
- `ack_state_machine_ok: false`
- `ack_state_machine` includes `cancel_no_ack_301_302` (`severity: error`).

---

## Prompt

I sent this ticket-cancel to MTS (code 301):

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cancel",
    "cancellationId": "can-9",
    "details": {"type": "ticket", "ticketId": "1000000001", "ticketSignature": "sigT", "code": 301}
  },
  "correlationId": "cancel-x9",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel",
  "version": "3.0"
}
```

MTS accepted it and replied with:

```json
{
  "content": {"type": "cancel-reply", "cancellationId": "can-9", "ticketId": "1000000001", "status": "accepted", "code": 0, "signature": "respSig9"},
  "correlationId": "cancel-x9",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel",
  "version": "3.0"
}
```

I'm about to send this cancel-ack. Is that correct?

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cancel-ack",
    "cancellationId": "can-9",
    "ticketId": "1000000001",
    "cancellationSignature": "respSig9",
    "acknowledged": true
  },
  "correlationId": "cancel-ack-9",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel-ack",
  "version": "3.0"
}
```
