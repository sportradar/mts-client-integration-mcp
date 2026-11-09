One ticket, two separate bets with different stakes — multibet for MTS, currency EUR.

Bet 1 — 10 EUR single:

```json
{
  "eventId": "sr:match:68306910",
  "id": "uof:3/sr:sport:1/90/12?total=2.25",
  "odds": 16700
}
```

Bet 2 — 25 EUR single:

```json
{
  "eventId": "sr:match:63110561",
  "id": "uof:3/sr:sport:2/223/1715?hcp=30",
  "odds": 28200
}
```

Build the Ticket 3.0 multibet placement request.

Use integrator **operator id**, **limit id**, and **channel** (type + ip + lang as schema requires); repo examples use E2E pair `9985` / `1409` — replace with your profile.
