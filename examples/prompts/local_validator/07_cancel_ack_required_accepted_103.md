# 07 — Accepted cancel (code 103), ACK missing

**Goal:** After MTS **accepts** a cancellation with code `103`, the client
**must** send a `ticket-cancel-ack` with `acknowledged: true`. Here the
exchange shows the accepted cancel response but no ACK was sent.

**Expected result:**
- `ack_state_machine_ok: false`
- `ack_state_machine` includes `cancel_ack_required_101_103_104_105`
  (`severity: error`).

---

## Prompt

I sent this ticket-cancel to MTS (code 103):

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cancel",
    "cancellationId": "can-1",
    "details": {"type": "ticket", "ticketId": "1000000001", "ticketSignature": "sigT", "code": 103}
  },
  "correlationId": "cancel-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel",
  "version": "3.0"
}
```

MTS accepted it and replied with:

```json
{
  "content": {"type": "cancel-reply", "cancellationId": "can-1", "ticketId": "1000000001", "status": "accepted", "code": 0, "signature": "respSig1"},
  "correlationId": "cancel-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel",
  "version": "3.0"
}
```

I did not send any acknowledgement. Can you audit this exchange?
