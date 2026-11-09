I'm mixing live and prematch on one accumulator for MTS. Stake 75 EUR in EUR.

Prematch selection:

```json
{
  "eventId": "sr:match:67018048",
  "id": "uof:3/sr:sport:1/37/800?total=1.5",
  "odds": 35800
}
```

Live selections:

```json
[
  {
    "eventId": "sr:match:72533852",
    "id": "uof:1/sr:sport:34/309/1714?hcp=3.5|setnr=2",
    "odds": 19200
  },
  {
    "eventId": "sr:match:72460886",
    "id": "uof:1/sr:sport:1/79/796?total=1.5",
    "odds": 140000
  }
]
```

Build the Ticket 3.0 placement request with all three selections combined.

Use integrator **operator id**, **limit id**, and **channel** (type + ip + lang as schema requires); repo examples use E2E pair `9985` / `1409` — replace with your profile.
