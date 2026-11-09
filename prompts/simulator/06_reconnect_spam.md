# 06 — Rapid reconnect attempts

**Goal:** Verify that the local simulator **records reconnect attempt timestamps**
when clients hammer the endpoint with repeated connection attempts. This supports
analysis of backoff and heartbeat behaviour — the mock logs attempts but does not
itself throttle or reject based on reconnect frequency.

**Expected result:**

- Multiple connect attempts in quick succession are accepted (or fail only for
  ordinary reasons, not an artificial spam penalty from this scenario).
- After several reconnects, session metrics include a **reconnect_attempts** log
  with timestamps (and remote address) for each attempt.

---

## Prompt

We're reviewing our reconnect logic and I want to see what the **local MTS
simulator** records when a client reconnects aggressively — the kind of pattern
you'd flag if someone wasn't backing off properly.

Start a mock session with reconnect logging enabled, then connect and disconnect
(or open several connections in a row) a handful of times in quick succession.
Place at least one ticket so we know the session is real.

When you wrap up, show me what the mock captured about those reconnect attempts —
timestamps and anything else it logged — so we can tell whether we'd catch noisy
client behaviour in a review.
