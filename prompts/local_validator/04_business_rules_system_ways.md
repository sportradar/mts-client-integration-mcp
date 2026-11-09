# 04 — Business rules: system, ways, and non-SR structure

**Goal:** A two-bet ticket that exercises the structural rules:
- Bet 1 is a **system** with `size: [2, 3]` (a recognised *Trixie* permutation)
  but one of its selections is **non-Sportradar (external)** content — not allowed in
  a system bet.
- Bet 2 is a **ways** node whose selections are on **two different events** — a ways
  node must group selections of the same event.

**Expected result:**
- `business_rules_ok: false`
- `business_rules` includes:
  - `predefined_system_sizes` → `severity: info` (matches *Trixie* `[2, 3]`)
  - `non_sr_in_system_forbidden` → `severity: error`, `maps_to_code: -214`
  - `ways_same_event` → `severity: error`, `maps_to_code: -333`

---

## Prompt

Review this ticket-placement for structural business-rule issues before I send
it to MTS.

```json
{
  "operatorId": "9985",
  "content": {
    "type": "ticket",
    "ticketId": "2337926715",
    "bets": [
      {
        "selections": [
          {
            "type": "system",
            "size": [2, 3],
            "selections": [
              {"type": "uf", "productId": "3", "eventId": "sr:match:1", "marketId": "1", "outcomeId": "1", "odds": {"type": "decimal", "value": "1.5"}},
              {"type": "uf", "productId": "3", "eventId": "sr:match:2", "marketId": "1", "outcomeId": "1", "odds": {"type": "decimal", "value": "1.8"}},
              {"type": "external", "event": "ext:match:99", "outcome": "ext-pre:9985:s1", "odds": {"type": "decimal", "value": "2.0"}, "expSettleTime": 1746000000000}
            ]
          }
        ],
        "stake": [{"type": "cash", "currency": "EUR", "amount": "10"}]
      },
      {
        "selections": [
          {
            "type": "ways",
            "selections": [
              {"type": "uf", "productId": "3", "eventId": "sr:match:10", "marketId": "1", "outcomeId": "1", "odds": {"type": "decimal", "value": "1.5"}},
              {"type": "uf", "productId": "3", "eventId": "sr:match:11", "marketId": "1", "outcomeId": "1", "odds": {"type": "decimal", "value": "1.6"}}
            ]
          }
        ],
        "stake": [{"type": "cash", "currency": "EUR", "amount": "10"}]
      }
    ],
    "context": {
      "channel": {"type": "internet", "ip": "212.7.5.2", "lang": "en"},
      "endCustomer": {"id": "user3454"},
      "limitId": 1409
    }
  },
  "correlationId": "H293vAko5G",
  "timestampUtc": 1745311871018,
  "operation": "ticket-placement",
  "version": "3.0"
}
```
