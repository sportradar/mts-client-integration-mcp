# 09 — Partial cash-out cumulative percentage

**Goal:** Verify cumulative partial cash-out tracking: MTS expects **percentage**
to be the running total cashed out, not the increment. Cash out 50% (`0.5`), then
80% cumulative (`0.8`) should succeed; sending `0.3` after `0.5` (the incremental
mistake) should be **rejected**.

**Expected result:**

- First partial cash-out at **0.5** → accepted.
- Second at **0.3** (lower than 0.5, treating percentage as delta) → rejected.
- Third at **0.8** (correct cumulative after 0.5) → accepted.
- Same ticket id across all three attempts.

---

## Prompt

We had a bug where partial cash-out **percentage** was sent as the increment
("another 30%") instead of the cumulative total ("80% of the original stake
after already cashing 50%"). I want to rehearse that on the **local MTS
simulator** before CI catches it again.

Use the same ticket id throughout. Cash out half the stake (`0.5`), then try
`0.3` like someone sending "30% more" — that should fail. Then send `0.8` as the
correct cumulative figure after the 50% — that should pass.

Report accept/reject for each step and explain which mistake the middle attempt
represents. Use separate connections per cash-out if that's how our wire client
would behave in production.
