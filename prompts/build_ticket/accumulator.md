Put together an accumulator for MTS — 50 EUR stake, EUR currency. These three prematch selections go on one ticket:

```json
[
  {
    "eventId": "sr:match:68306910",
    "id": "uof:3/sr:sport:1/90/12?total=2.25",
    "odds": 16700
  },
  {
    "eventId": "sr:match:63110561",
    "id": "uof:3/sr:sport:2/223/1715?hcp=30",
    "odds": 28200
  },
  {
    "eventId": "sr:match:71508942",
    "id": "uof:3/sr:sport:1/818/1839?total=1.5",
    "odds": 123000
  }
]
```

I need the ticket-placement JSON ready to send.

Use integrator **operator id**, **limit id**, and **channel** (type + ip + lang as schema requires); repo examples use E2E pair `9985` / `1409` — replace with your profile.
