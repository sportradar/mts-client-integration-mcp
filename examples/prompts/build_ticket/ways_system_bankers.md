I need the full ways + system + bankers shape for MTS. Stake 45 EUR in EUR.

Banker selections (must win):

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
  }
]
```

Ways nest on `sr:match:70688082`:

```json
[
  {
    "eventId": "sr:match:70688082",
    "id": "uof:3/sr:sport:1/18/12?total=1.5",
    "odds": 10100
  },
  {
    "eventId": "sr:match:70688082",
    "id": "uof:3/sr:sport:1/1/1",
    "odds": 22000
  }
]
```

Outer selection (banker outside the system):

```json
{
  "eventId": "sr:match:71508942",
  "id": "uof:3/sr:sport:1/818/1839?total=1.5",
  "odds": 123000
}
```

System size [1]. Build the Ticket 3.0 request.

Use integrator **operator id**, **limit id**, and **channel** (type + ip + lang as schema requires); repo examples use E2E pair `9985` / `1409` — replace with your profile.
