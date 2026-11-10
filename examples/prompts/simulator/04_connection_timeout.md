# 04 — Long-lived connection timeout

**Goal:** Verify that the local simulator closes WebSocket connections after the
configured connection lifetime (production default is two hours). Locally this
should be exercised with a **short timeout** so the drop happens within seconds,
not hours — optionally by fast-forwarding the timer rather than waiting.

**Expected result:**

- A ticket-placement works while the connection is fresh.
- After the connection lifetime expires (or the timer is fast-forwarded), open
  connections are closed by the simulator.
- A new connection after the drop can place tickets normally again.

---

## Prompt

We need to rehearse what happens when an MTS WebSocket **ages out** — connections
don't live forever and the client is supposed to handle a clean drop and reconnect.

Can you test this on the **local MTS simulator** with the long-connection timeout
behaviour enabled? Don't make me wait two hours — configure a short lifetime for
local testing, or skip ahead in time if the mock supports that. Place a ticket
while connected, trigger the timeout, confirm the connection actually closes, then
open a fresh connection and place again.

Summarise the close reason if you see one, and whether traffic recovers on the
new connection.
