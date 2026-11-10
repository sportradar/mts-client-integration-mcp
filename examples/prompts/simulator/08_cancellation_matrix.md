# 08 — Cancellation reply matrix

**Goal:** Verify that the local simulator returns fixture **cancel-reply** responses
for ticket-cancel requests across the standard cancellation codes (101, 103, 104,
105, 301, 302). Each code should get a well-formed reply so ACK/nACK rules can
be exercised downstream.

**Expected result:**

- Each ticket-cancel sent with codes **101**, **103**, and **301** (at minimum)
  receives a cancel-reply on the wire.
- Replies are structurally valid and indicate accepted or rejected status per the
  mock's cancellation matrix rules.
- Exchanges are captured in the session wire log for later validation.

---

## Prompt

We're about to test our **cancellation ACK handling** and I want fixture cancel
responses locally before we depend on a real MTS environment.

On the **local MTS simulator** with the cancellation matrix behaviour enabled,
send ticket-cancel requests for a few different cancellation codes — at least
101, 103, and 301. They don't all need the same ticket history; I mainly want to
see that each code gets a proper cancel-reply back.

Pull the wire log when you're done and summarise what status each code got. If any
code behaves differently from the others, call that out — we'll need that for ACK
rules later.
