# 01 — Connection blocked while placing

**Goal:** Reproduce the connectivity scenario where MTS blocks the client's
connection while a bet is being placed. When the connection is down, a placement
must not reach MTS. After the connection is restored, placement should work
normally again.

**Expected result:**

- With the simulator running and the connection healthy, a normal ticket-placement
  is accepted.
- After the connection is blocked, trying to place another ticket should fail —
  nothing should complete on the wire.
- After the block is lifted, the next placement is accepted again.
- The session log from the simulator should show successful exchanges for the
  before and after placements, but no completed round-trip for the attempt made
  while blocked.

---

## Prompt

We're preparing for CI and I want to rehearse a connectivity scenario locally
before anyone touches staging.

Here's the situation: our connection to MTS gets blocked, we try to place a bet
while we're down, then the connection comes back and we place again.

Can you run that against the **local MTS simulator**? Start from a clean mock
session with normal connectivity settings. First confirm things work end-to-end
by placing a simple single prematch ticket. Then simulate the connection being
blocked — as if the platform had cut us off. While we're blocked, try placing
another ticket; that one must not get through. After that, simulate the unblock
and place once more — that one should go through like the first.

When you're done, pull the wire log from the mock session and walk me through
what happened at each step. I want to know whether the blocked attempt stayed off
the wire and whether the two good placements show up as accepted ticket-replies.

---

**Exmple Cursor result**

I'll explore how the local MTS simulator handles sessions, connectivity blocking, and ticket placement so we can rehearse your scenario end-to-end.


Reading the MCP tool schemas, then running the full connectivity rehearsal against the local simulator.


Running the full connectivity rehearsal as a scripted scenario against the local simulator.


The connectivity rehearsal completed successfully against the local MTS simulator. All checks passed.

## Scenario summary

| Step | Action | Result |
|------|--------|--------|
| 0 | Clean start (`realistic_mix`, normal connectivity) | `ws://127.0.0.1:8765`, `blocked: false` |
| 1 | Place single prematch ticket (`t-90ed5d53a142`, €10) | **Accepted** — `ticket-reply`, code 0 |
| 2 | `inject(connection_blocked)` | Platform cut-off active, `blocked: true` |
| 3 | Place while blocked (`t-9b7c2c5f200f`, €15) | **Rejected at handshake** — close code `1001`, no reply |
| 4 | `inject(connection_unblocked)` | Connectivity restored, `blocked: false` |
| 5 | Place after unblock (`t-18f2a8e102e1`, €20) | **Accepted** — `ticket-reply`, code 0 |

---

## Wire log walkthrough (`mock-e03e744dc634`)

Four entries total — exactly two outbound/inbound pairs, nothing from the blocked attempt:

```
[0] outbound  ticket-placement  type=ticket        ticketId=t-90ed5d53a142
[1] inbound   ticket-placement  type=ticket-reply  status=accepted  code=0  ticketId=t-90ed5d53a142
[2] outbound  ticket-placement  type=ticket        ticketId=t-18f2a8e102e1
[3] inbound   ticket-placement  type=ticket-reply  status=accepted  code=0  ticketId=t-18f2a8e102e1
```

**Step 1 — baseline placement (normal connectivity)**  
`t-90ed5d53a142` went out on the wire and came back as an accepted `ticket-reply` (entries 0–1). This confirms end-to-end placement works before any disruption.

**Step 2 — platform cut-off**  
`connection_blocked` closed active WebSocket connections with code `1001` and set the server to reject new handshakes immediately.

**Step 3 — blocked placement**  
`t-9b7c2c5f200f` never reached the wire. The client got `connection_close_code: 1001` with no `ticket-reply`. That ticket ID does not appear anywhere in the wire log — the simulator rejects the connection before the message handler runs.

**Step 4 — unblock**  
`connection_unblocked` cleared the block flag; new connections are accepted again.

**Step 5 — recovery placement**  
`t-18f2a8e102e1` went out and came back accepted (entries 2–3), same pattern as the first good placement.

**Session metrics:** `messages_in: 2`, `messages_out: 2`, `rate_limit_rejections: 0` — consistent with exactly two successful round-trips.

---

## Answers to your specific questions

- **Did the blocked attempt stay off the wire?** Yes. `t-9b7c2c5f200f` is absent from the wire log; only the two good placements appear as outbound `ticket-placement` messages.
- **Do the two good placements show accepted ticket-replies?** Yes. Both `t-90ed5d53a142` and `t-18f2a8e102e1` have matching inbound `ticket-reply` entries with `status: accepted` and `code: 0`.

When the platform cuts you off, bets cannot reach MTS and nothing is logged server-side; once connectivity returns, placements flow normally again.

