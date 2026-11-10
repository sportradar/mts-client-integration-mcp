# 02 — Oversized WebSocket frame

**Goal:** Verify that the local simulator enforces the Ticket 3.0 frame-size limit
(32 KB per frame, at most four frames, 128 KB total). Sending a single frame that
exceeds the limit should cause the connection to close with an appropriate WebSocket
error — not a silent failure or a normal ticket-reply.

**Expected result:**

- A normal-sized ticket-placement is accepted when the simulator is configured for
  frame splitting behaviour.
- A deliberately oversized payload (well beyond 32 KB in one frame) causes the
  connection to drop with close code **1009** (or equivalent frame violation).
- No accepted ticket-reply is returned for the oversized send.

---

## Prompt

We're wiring up our MTS client and I want to sanity-check the **32 KB WebSocket
frame limit** locally before we hit it in integration.

Can you exercise this on the **local MTS simulator** with frame-split handling
enabled? Start a fresh mock session, send a normal single prematch ticket first so
we know the baseline works, then send something intentionally too large — one
frame that blows past 32 KB.

Tell me what happened to the connection and whether the simulator rejected it the
way a real MTS endpoint would, rather than accepting or hanging.
