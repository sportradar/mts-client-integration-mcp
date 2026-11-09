# 07 — Alternative stake offer and resubmit

**Goal:** Verify the alt-stake flow: the first ticket-placement is **rejected** with
an alternative stake suggestion; resubmitting the same bet with a proper reference
to that offer (alt-stake ref carrying the rejected ticket id and signature) is
**accepted**.

**Expected result:**

- First placement → rejected ticket-reply containing an alt-stake offer (and
  signature to reference).
- Resubmit referencing the alt-stake offer from the first reply → accepted
  ticket-reply.
- Both exchanges appear in the session wire log.

---

## Prompt

Our client has to handle **alternative stake offers** — MTS rejects the first
placement but tells us a stake that would be accepted, and we're supposed to
resubmit with a reference back to that offer.

Can you walk through that flow on the **local MTS simulator** with alt-stake
behaviour enabled? Place a single prematch ticket, expect the rejection and read
the offer off the reply, then send the bet again on the **same connection** with
the proper alt-stake reference filled in from what came back.

Tell me whether the first one was rejected with an offer and whether the resubmit
was accepted. Include the key fields from both replies so I can sanity-check them.
