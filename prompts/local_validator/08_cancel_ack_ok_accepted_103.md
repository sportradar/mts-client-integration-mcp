# 08 — Accepted cancel (code 103), ACK sent correctly

**Goal:** Same accepted-103 flow as #07, but this time the client is sending the
correct `ticket-cancel-ack` (`acknowledged: true`, signature matching the
response).

**Expected result:**
- `ack_state_machine_ok: true`
- No `cancel_ack_required_101_103_104_105` and no
  `ack_matches_response_signature` findings.

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

Now I'm sending this ticket-cancel-ack. Is it correct?

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cancel-ack",
    "cancellationId": "can-1",
    "ticketId": "1000000001",
    "cancellationSignature": "respSig1",
    "acknowledged": true
  },
  "correlationId": "cancel-ack-1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel-ack",
  "version": "3.0"
}
```
