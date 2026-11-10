# 03 — Wire rate limiting

**Goal:** Verify that the local simulator applies throughput limiting on the
WebSocket (integration profile: roughly 10 requests per second). A burst of
ticket traffic faster than the limit should produce fixture rejections for the
excess requests, not unlimited accepts.

**Expected result:**

- The first few placements in a rapid burst are accepted normally.
- Further sends in the same burst within one second receive **rejected**
  ticket-replies (rate-limit behaviour), not silent drops.
- Session metrics reflect multiple rate-limit rejections after the burst.

---

## Prompt

Our client can fire tickets quickly under load and I want to see how MTS-style
**rate limiting** behaves before we connect to a shared integration environment.

Can you run a burst test on the **local MTS simulator** with rate limiting turned
on (integration throughput, not production)? Open one connection and send a bunch
of ticket-placements back-to-back — more than ten within a second or so.

Walk me through how many were accepted vs rejected, and whether the rejections
look like proper ticket-replies rather than connection failures.
