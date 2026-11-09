# 11 — Cancel ACK signature does not match the response

**Goal:** The acknowledgement is present and `acknowledged: true` (so the
matrix requirement is satisfied), but its `cancellationSignature` does not match
the `signature` from the paired cancel response. The signature echo must match.

**Expected result:**
- `ack_state_machine_ok: false`
- `ack_state_machine` includes `ack_matches_response_signature`
  (`severity: error`).
- `cancel_ack_required_101_103_104_105` is **not** raised (an ACK was sent).

---

## Prompt

I sent this ticket-cancel to MTS (code 103):

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cancel",
    "cancellationId": "can-1",
    "details": {"type": "ticket", "ticketId": "2337926713", "ticketSignature": "sigT", "code": 103}
  },
  "correlationId": "cancel-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel",
  "version": "3.0"
}
```

MTS accepted it and replied with signature `respSig1`:

```json
{
  "content": {"type": "cancel-reply", "cancellationId": "can-1", "ticketId": "2337926713", "status": "accepted", "code": 0, "signature": "respSig1"},
  "correlationId": "cancel-x1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel",
  "version": "3.0"
}
```

Now I'm sending this cancel-ack. Does it echo the response signature correctly?

```json
{
  "operatorId": "9985",
  "content": {
    "type": "cancel-ack",
    "cancellationId": "can-1",
    "ticketId": "2337926713",
    "cancellationSignature": "WRONGsig",
    "acknowledged": true
  },
  "correlationId": "cancel-ack-1",
  "timestampUtc": 1745311871018,
  "operation": "ticket-cancel-ack",
  "version": "3.0"
}
```
