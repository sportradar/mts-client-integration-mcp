# 05 — Sudden disconnect without block

**Goal:** Verify behaviour when the simulator **drops all active connections once**
without entering a blocked state. The client should be able to reconnect immediately
afterward — unlike a full connection block, new handshakes are still accepted.

**Expected result:**

- An active connection can exchange tickets normally before the drop.
- After the forced disconnect, existing connections are closed.
- Reconnecting right away works; a new ticket-placement is accepted.
- The mock is **not** in a blocked state — only the connections were torn down.

---

## Prompt

Sometimes the platform kills our WebSocket without a long block — the line just
drops and we're expected to **reconnect and carry on**, not sit in a prolonged
outage.

Can you simulate that on the **local MTS simulator**? Get a session going, place
a ticket, then trigger a one-shot disconnect of all live connections (not the same
as blocking new connections entirely). Right after the drop, reconnect and place
again.

I want to confirm we can get back on the wire immediately and that the mock didn't
enter a "reject all new connections" mode — only the existing sockets were closed.

---
**Example Cursor Reuslt**

Ran the full scenario on the local MTS simulator (`ws://127.0.0.1:8765`). Here's what happened.

## Result: reconnect works immediately after a one-shot drop

| Step | What happened |
|------|----------------|
| 1. Session + first ticket | Connected, placed `t-reconnect-demo-before` → **accepted** |
| 2. Live connection held | `mock_status` showed **`connections: 1`**, **`blocked: false`** |
| 3. `inject(event="force_disconnect")` | Socket dropped with **code 1001**, reason `"force disconnect by inject"` |
| 4. Immediate reconnect | New handshake in **3.5 ms** |
| 5. Second ticket | Placed `t-reconnect-demo-after` → **accepted** |
| 6. Post-drop status | **`blocked: false`** — mock did **not** enter reject-all mode |

Terminal output from the demo:

```
PLACED_BEFORE status=accepted ticket=t-reconnect-demo-before
CONNECTION_LIVE
DROPPED code=1001 reason='force disconnect by inject'
RECONNECTED elapsed_ms=3.5
PLACED_AFTER status=accepted ticket=t-reconnect-demo-after
DONE ok
```

## How this differs from a full outage

The simulator has two distinct inject events:

| Event | Drops live sockets | Blocks new connections |
|-------|-------------------|------------------------|
| **`force_disconnect`** | Yes (1001) | **No** — reconnect right away |
| **`connection_blocked`** | Yes | **Yes** — rejects handshakes until `connection_unblocked` |

`force_disconnect` is the right tool for "platform killed our wire, we reconnect and carry on."

## How to reproduce

**1. Start the mock** (MCP or Inspector — must stay in one persistent session):

```
start_mock(scenarios=["realistic_mix"])
```

**2. Hold a live connection, place, then inject:**

```
inject(event="force_disconnect")
```

**3. Reconnect and place again** — your client should handshake immediately; no unblock step needed.

Trigger `inject(force_disconnect)` via MCP once you see `CONNECTION_LIVE` in the script output.

**Bottom line:** the mock only closed existing sockets. New connections were accepted immediately, and placement worked on the first retry after reconnect. That's the behavior you want for a platform-side wire drop, not a prolonged outage.