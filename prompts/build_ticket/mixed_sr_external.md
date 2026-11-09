Accumulator mixing UOF prematch with an external selection. Stake 35 EUR EUR.

Sportradar selection:

```json
{
  "eventId": "sr:match:68306910",
  "id": "uof:3/sr:sport:1/90/12?total=2.25",
  "odds": 16700
}
```

External selection:

```json
{
  "type": "external",
  "event": "ext:match:8821",
  "outcome": "ext-pre:9985:away",
  "odds": 18500,
  "exp_settle_time": 1780502400000
}
```

Build the ticket-placement request.

Use integrator **operator id**, **limit id**, and **channel** (type + ip + lang as schema requires); repo examples use E2E pair `9985` / `1409` — replace with your profile.
