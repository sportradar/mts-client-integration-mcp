# MTS Client Integration MCP

Local Python MCP server for MTS Transaction 3.0 client integration. AI agents
and integrators use it to decode rejection codes, validate Ticket 3.0 requests,
build golden tickets, and exercise connectivity with a local WebSocket mock.

## Features

- **Rejection decoder** — `lookup_rejection_code`
- **Local validator** — JSON Schema, envelope, business rules, ACK state machine (`validate_ticket_request`)
- **Golden ticket builder** — `build_placement`, `build_cashout`, `build_ext_settlement` (34 shapes)
- **Local simulator** — `start_mock`, `inject`, `stop_mock`, `send_to_mock`
- **MCP resources** — Ticket 3.0 schemas, builder templates, session-state docs
- **Python Ticket 3.0 models** — `src/mts_client_integration/models/ticket3/`

## Requirements

- Python **3.14+**
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone https://github.com/sportradar/mts-client-integration-mcp.git
cd mts-client-integration-mcp
uv sync
```

If you need a non-default package index, use `.envrc.example` → `.envrc` and
`direnv allow` — see [Contributing](CONTRIBUTING.md#development-setup).

## MCP client setup

### Cursor

1. Clone this repository and run `uv sync` in it.
2. Add an MCP server entry in Cursor — either in the workspace
   (`.cursor/mcp.json`) or globally (`~/.cursor/mcp.json`):

   ```json
   {
     "mcpServers": {
       "mts-client-integration": {
         "command": "uv",
         "args": [
           "--directory",
           "/path/to/mts-client-integration-mcp",
           "run",
           "mts-mcp-server"
         ]
       }
     }
   }
   ```

3. Set `--directory` to the absolute path of the cloned repository.
4. Restart Cursor or reload MCP servers (**Settings → MCP**, or the MCP panel
   refresh action).

Once connected, the tools listed below are available to the agent in that
workspace.

### Claude Desktop

Add the same command to your Claude Desktop MCP config (path varies by OS), for
example `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS:

```json
{
  "mcpServers": {
    "mts-client-integration": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mts-client-integration-mcp",
        "run",
        "mts-mcp-server"
      ]
    }
  }
}
```

Restart Claude Desktop after saving.

## Run locally

```bash
uv run mts-mcp-server
```

Alternative entrypoint:

```bash
uv run python src/server.py
```

The server uses stdio transport (default for Cursor). It speaks JSON-RPC over
stdin/stdout, so it is not meant for interactive typing in a terminal.

### MCP Inspector

```bash
uv run fastmcp dev inspector src/server.py:create_server --project .
```

Open the URL printed in the terminal (often `http://localhost:6274`), select
**STDIO** if prompted, and click **Connect**.

### Smoke tests (CLI)

```bash
uv run fastmcp list --command "uv run mts-mcp-server"

uv run fastmcp call \
  --command "uv run mts-mcp-server" \
  --target lookup_rejection_code \
  --input-json '{"code": -702}' \
  --json
```

## MCP Tools

The server exposes tools over stdio (JSON-RPC).

---

### Rejection Decoder

MCP tool handler: `lookup_rejection_code`

Look up the canonical MTS rejection message for a validation or response code.

**When to use:** An integrator received a numeric rejection code from MTS and
needs the official message text, and optionally reproduction steps or fix
suggestions when the catalog entry includes them. Pass request context when the
same code means different things for different Ticket 3.0 operations.

**Parameters**

| Parameter                  | Type      | Required | Description                                                                                                                                                          |
|----------------------------|-----------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `code`                     | `integer` | yes      | MTS rejection code. Both `-702` and `702` are accepted (normalized to negative).                                                                                     |
| `ticket_context`           | `object`  | no       | Context from the rejected Ticket 3.0 request. Only `operation` is read today; extra keys are ignored.                                                                |
| `ticket_context.operation` | `string`  | no       | Top-level `operation` field from the outbound request JSON (e.g. `ticket-placement`, `cashout-build`). Required when the rejection code is shared across operations. |

**Response**

| Field                  | Type             | Description                                                                                                                                         |
|------------------------|------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| `code`                 | `integer`        | Normalized rejection code (negative).                                                                                                               |
| `message`              | `string \| null` | Canonical rejection message, or `null` when the code is unknown.                                                                                    |
| `found`                | `boolean`        | `true` when the code exists in the catalog.                                                                                                         |
| `operations`           | `string[]`       | Operation(s) associated with the matched variant (when `found`).                                                                                    |
| `category`             | `string \| null` | Optional category label from the catalog.                                                                                                           |
| `ambiguous`            | `boolean`        | `true` when multiple variants exist and no `operation` was provided; `message` then lists all variants. Retry with the operation from your request. |
| `steps_to_reproduce`   | `string[]`       | Optional ordered steps to reproduce the rejection. Omitted when the catalog has none.                                                               |
| `fix_suggestions`      | `string[]`       | Optional suggested fixes. Omitted when the catalog has none.                                                                                      |

<details>
<summary><strong>Tool Examples</strong></summary>

Code only (unambiguous codes):

```json
{
  "code": -702
}
```

With operation disambiguation:

```json
{
  "code": -702,
  "ticket_context": {
    "operation": "ticket-placement"
  }
}
```

Equivalent shortcut:

```json
{
  "code": -101,
  "operation": "cashout-build"
}
```

Success response (guidance fields omitted when empty in the catalog):

```json
{
  "code": -702,
  "message": "Liability EUR XXX is over Bet liability limit EUR YYY on Limit ID(Bookmaker or Global) level, Selection: `<SelectionURL>`, Match: `<Match ID>`",
  "found": true,
  "operations": [
    "ticket-placement"
  ],
  "category": null,
  "ambiguous": false
}
```

When the catalog entry includes guidance:

```json
{
  "code": -702,
  "message": "Liability EUR XXX is over Bet liability limit EUR YYY on Limit ID(Bookmaker or Global) level, Selection: `<SelectionURL>`, Match: `<Match ID>`",
  "found": true,
  "operations": [
    "ticket-placement"
  ],
  "category": null,
  "ambiguous": false,
  "steps_to_reproduce": [
    "Place a ticket with stake above the bookmaker liability limit for the selection."
  ],
  "fix_suggestions": [
    "Reduce stake or remove the selection from the bet."
  ]
}
```

Unknown code:

```json
{
  "code": -99999,
  "message": null,
  "found": false,
  "operations": [],
  "category": null,
  "ambiguous": false
}
```
</details>

**Example agent prompt**

> I got MTS rejection code -702 on a ticket-placement request. What does it mean?

The agent should call
`lookup_rejection_code(-702, ticket_context={"operation": "ticket-placement"})`
and read `message`, plus `steps_to_reproduce` and `fix_suggestions` when
present.

---

### Local Validator

MCP tool handler: `validate_ticket_request`

Validate a Ticket 3.0 request payload before sending it to MTS, across four
layers: JSON Schema, typed envelope, business rules, and an ACK / nACK state
machine over the optional `session_state`.

**When to use:** Building or reviewing outbound Ticket 3.0 JSON and you want to
catch, locally, the issues that otherwise surface as MTS rejections. The
business-rule layer covers the selection cap (100), positive stake, minimum
decimal odds (1.01), currency format, system `size` validity and predefined
permutations (Trixie/Yankee/…), ways same-event, non-SR-in-system and
banker-on-non-SR, Custom Bet anti-multiplication and caps, cumulative partial
cash-out percentage,
channel/language expectations, and the 32 KB × 4 frame-size limit. The ACK
layer enforces the cancellation ACK matrix, the ticket-placement
acknowledgement flow (`ticket-reply` → `ticket-ack`/nACK), and validates ACK
payload shapes and signature matching.

**Parameters**

| Parameter               | Type                    | Required | Description                                                                             |
|-------------------------|-------------------------|----------|-----------------------------------------------------------------------------------------|
| `payload`               | `object` or `string`    | yes      | The single outbound Ticket 3.0 request envelope being validated (same JSON sent over the WebSocket). Exactly one message; earlier ones go in `session_state`. |
| `operation`             | `string`                | no       | Optional cross-check; must match `payload.operation` when provided.                     |
| `session_state`         | `object[]` or `string`  | no       | Prior wire messages for this session (raw envelopes or a pasted log dump), in chronological order and excluding `payload`, for stateful and ACK-flow rules. |
| `reference_time_utc_ms` | `integer`               | no       | Clock for `timestampUtc` checks; defaults to now.                                       |
| `serialized_bytes`      | `integer`               | no       | Byte length of the serialized message for the frame-size rule; defaults to encoded `payload` size. |

Direction is from the integrator's (client's) point of view: *outbound* =
client → MTS, *inbound* = MTS → client (responses whose `content.type` ends in
`-reply`). `session_state` accepts either structured entries
(`{"direction": "outbound"｜"inbound", "message": {<envelope>}}`; `direction` is
optional and inferred) or a raw log string with `->`/`<-` markers. Messages are
paired by `correlationId`. See the `mts://schemas/session-state` MCP resource
for the full shape.

**Response**

| Field                  | Type       | Description                                                          |
|------------------------|------------|----------------------------------------------------------------------|
| `schema_ok`            | `boolean`  | `true` when JSON Schema validation passes.                           |
| `schema_errors`        | `object[]` | Issues from JSON Schema (`rule_id`: `jsonschema`).                   |
| `envelope_ok`          | `boolean`  | `true` when Pydantic envelope parsing passes.                        |
| `envelope_errors`      | `object[]` | Envelope/type issues (`rule_id`: `envelope` or `operation_mismatch`). |
| `business_rules_ok`    | `boolean`  | `true` when no business rule has `error` severity.                   |
| `business_rules`       | `object[]` | Business-rule findings; each has `rule_id`, `severity`, `path`, `message`, `maps_to_code`. |
| `ack_state_machine_ok` | `boolean`  | `true` when no ACK check has `error` severity.                       |
| `ack_state_machine`    | `object[]` | ACK / nACK findings; each has `rule_id`, `severity`, `message`, `correlation_id`, `ticket_id`. |
| `session_state_errors` | `object[]` | Unparseable or unmatched `session_state` messages (`index`, `message`). |

Schema/envelope error object: `{ "path": "$.content...", "message": "...", "rule_id": "..." }`.
Business-rule and ACK issues carry a `severity` of `error`, `warning`, or
`info`; only `error` flips the corresponding `*_ok` flag.

<details>
<summary><strong>Tool Examples</strong></summary>

Valid ticket (minimal single):

```json
{
  "payload": {
    "operatorId": "9985",
    "content": {
      "type": "ticket",
      "ticketId": "Ticket_0001",
      "bets": [{
        "selections": [{
          "type": "uf",
          "productId": "3",
          "eventId": "sr:match:10000001",
          "marketId": "1",
          "outcomeId": "2",
          "odds": {"type": "decimal", "value": "1.32"}
        }],
        "stake": [{"type": "cash", "currency": "EUR", "amount": "10"}]
      }],
      "context": {
        "channel": {"type": "internet", "ip": "127.0.0.1", "lang": "EN"},
        "endCustomer": {"id": "user_0001"},
        "limitId": 1409
      }
    },
    "correlationId": "CRL0000001",
    "timestampUtc": 1678876155000,
    "operation": "ticket-placement",
    "version": "3.0"
  }
}
```

Success response:

```json
{
  "schema_ok": true,
  "schema_errors": [],
  "envelope_ok": true,
  "envelope_errors": [],
  "business_rules_ok": true,
  "business_rules": [],
  "ack_state_machine_ok": true,
  "ack_state_machine": [],
  "session_state_errors": []
}
```

Schema violation (missing `limitId`):

```json
{
  "schema_ok": false,
  "schema_errors": [
    {
      "path": "$.content.context",
      "message": "'limitId' is a required property",
      "rule_id": "jsonschema"
    }
  ],
  "envelope_ok": true,
  "envelope_errors": []
}
```

Follow-up partial cash-out sent as an increment (`0.3`) after a prior `0.5`,
with the placement and first cash-out supplied via `session_state`:

```json
{
  "schema_ok": true,
  "business_rules_ok": false,
  "business_rules": [
    {
      "rule_id": "cashout_percentage_monotonic",
      "severity": "error",
      "path": "$.content.details.percentage",
      "message": "Cash-out percentage 0.3 is lower than a previous value (0.5).",
      "maps_to_code": -211
    },
    {
      "rule_id": "cashout_cumulative_percentage",
      "severity": "warning",
      "path": "$.content.details.percentage",
      "message": "This is a follow-up partial cash-out ... 'percentage' must be the cumulative fraction ..., not the incremental amount.",
      "maps_to_code": -211
    }
  ]
}
```

</details>

**Example agent prompts**

Copy-paste integrator-style prompts for exercising `validate_ticket_request` live in
[`prompts/local_validator/`](prompts/local_validator/). Each file includes the
full chat message, prior exchange context where needed, and the expected
validator output.

| # | Prompt example | Exercises |
|---|----------------|-----------|
| 01 | [`01_schema_pass.md`](prompts/local_validator/01_schema_pass.md) | Valid ticket-placement → all layers green |
| 02 | [`02_schema_fail.md`](prompts/local_validator/02_schema_fail.md) | Missing required field → `schema_ok: false` |
| 03 | [`03_business_rules_stake_odds_currency.md`](prompts/local_validator/03_business_rules_stake_odds_currency.md) | Positive stake, min odds, currency format |
| 04 | [`04_business_rules_system_ways.md`](prompts/local_validator/04_business_rules_system_ways.md) | Predefined system, ways same-event, non-SR-in-system |
| 05 | [`05_cashout_cumulative_bug.md`](prompts/local_validator/05_cashout_cumulative_bug.md) | Partial cash-out sent as increment (`0.5` → `0.3`) |
| 06 | [`06_cashout_cumulative_ok.md`](prompts/local_validator/06_cashout_cumulative_ok.md) | Partial cash-out sent cumulatively (`0.5` → `0.8`) |
| 07 | [`07_cancel_ack_required_accepted_103.md`](prompts/local_validator/07_cancel_ack_required_accepted_103.md) | Accepted cancel 103, ACK missing |
| 08 | [`08_cancel_ack_ok_accepted_103.md`](prompts/local_validator/08_cancel_ack_ok_accepted_103.md) | Accepted cancel 103, ACK present |
| 09 | [`09_cancel_no_ack_accepted_301.md`](prompts/local_validator/09_cancel_no_ack_accepted_301.md) | Accepted cancel 301, ACK must NOT be sent |
| 10 | [`10_cancel_nack_on_rejected.md`](prompts/local_validator/10_cancel_nack_on_rejected.md) | Rejected cancel requires nACK |
| 11 | [`11_cancel_ack_signature_mismatch.md`](prompts/local_validator/11_cancel_ack_signature_mismatch.md) | ACK signature ≠ response signature |
| 12 | [`12_ticket_ack_required_accepted.md`](prompts/local_validator/12_ticket_ack_required_accepted.md) | Accepted ticket, ACK missing (info) |
| 13 | [`13_ticket_ack_ok_accepted.md`](prompts/local_validator/13_ticket_ack_ok_accepted.md) | Accepted ticket, ACK present |
| 14 | [`14_ticket_nack_failed_booking.md`](prompts/local_validator/14_ticket_nack_failed_booking.md) | Accepted ticket, nACK signals failed booking |
| 15 | [`15_ticket_ack_on_rejected_warning.md`](prompts/local_validator/15_ticket_ack_on_rejected_warning.md) | Rejected ticket should not be ACKed |

The agent should call `validate_ticket_request` with the envelope JSON from the prompt
as `payload`. For multi-message scenarios (cash-out follow-ups, cancel/ticket
ACK flows), build `session_state` from the prior exchanges described in the
prompt, or pass a raw log string with `->`/`<-` markers. Report findings by
layer and severity: `error` flips the corresponding `*_ok` flag;
`warning`/`info` findings are advisory. Use the linked file's **Expected
result** section when verifying behavior.

See also [`prompts/local_validator/README.md`](prompts/local_validator/README.md)
for notes on fixed timestamps in the samples.

---

### Golden Ticket Builder

MCP tools: **`build_placement`**, **`build_cashout`**, **`build_ext_settlement`**, plus **`list_ticket_shapes`**.

Each tool takes a **shape** (preset id) and a **typed params object** validated by Pydantic — the MCP tool schema is the contract (required fields, patterns, enums). Presets only supply **fixed structural defaults** (`bet_type`, `size`, `partial`, `settlement_level`). You must supply **every business value** (`operator_id`, `limit_id`, `channel`, odds, stake, cashout `code`/`percentage`, …) from the integrator or odds feed — nothing is invented or merged from environment variables.

**When to use:** Build schema-conformant Ticket 3.0 request JSON for tests or demos. Call `validate_ticket_request` on the returned `payload` before sending to real MTS.

**Discovery workflow**

1. `list_ticket_shapes()` — each entry names `tool`, `required_params`, and `description`.
2. Read **`mts://templates/{shape}`** — fixed defaults, required fields, JSON Schema fragment from the model, full **`example_params`**.
3. Call the matching tool with complete params (see **`mts://templates/builder-schema`** for all three param models).

**Tools**

| Tool | Shapes | Params model |
|------|--------|----------------|
| `build_placement` | Placement presets | `PlacementBuildParams` |
| `build_cashout` | Cashout presets | `CashoutBuildParams` |
| `build_ext_settlement` | Ext-settlement presets | `ExtSettlementBuildParams` |

**Response:** `{ "shape", "operation", "payload" }` — `payload` is the wire envelope.

**MCP resources**

| URI | Description |
|-----|-------------|
| `mts://schemas/ticket3/request` | Ticket 3.0 request JSON Schema |
| `mts://schemas/ticket3/response` | Ticket 3.0 response JSON Schema |
| `mts://templates/builder-schema` | `model_json_schema()` for the three param models |
| `mts://templates/{shape}` | `describe_shape(shape)` — defaults, required_params, example |
| `mts://integration/envelope-context` | How to obtain operator/limit/channel/end-customer values |

**Example (`build_placement`, accumulator)**

```json
{
  "shape": "accumulator",
  "params": {
    "operator_id": "<your-operator-id>",
    "limit_id": 123,
    "channel": {"type": "internet", "ip": "127.0.0.1", "lang": "en"},
    "selections": [
      {"event_id": "sr:match:1", "market_id": "1", "outcome_id": "1", "odds": "1.5", "product_id": "3"},
      {"event_id": "sr:match:2", "market_id": "1", "outcome_id": "1", "odds": "1.8", "product_id": "3"},
      {"event_id": "sr:match:3", "market_id": "1", "outcome_id": "1", "odds": "2.0", "product_id": "3"}
    ],
    "stake": "10",
    "currency": "EUR"
  }
}
```

### Targeted local simulator

Fixture-driven WebSocket mock for client integration scenarios.

#### Tools

| Tool | Purpose |
|------|---------|
| `list_mock_scenarios` | Catalog of scenario IDs, bundles, inject events |
| `start_mock` | Boot `ws://127.0.0.1:<port>` + stub OAuth |
| `inject` | `connection_blocked`, `force_disconnect`, `fast_forward_timer`, … |
| `stop_mock` | Shutdown; returns `wire_log` for `validate_ticket_request` |
| `mock_status` | Poll running mock |
| `send_to_mock` | Send payload(s) to the running mock over its WebSocket; returns replies |

#### Quick start

```text
start_mock(scenarios=["realistic_mix"])
→ point client at ws_url
→ place tickets
stop_mock() → wire_log → validate_ticket_request(session_state=wire_log)
```

### Example flows

**Connection blocked:** `start_mock()` → `inject(event="connection_blocked")` → bet must
not appear in `wire_log` → `inject(event="connection_unblocked")` → bet succeeds.

**Token handover (2h reconnect):** `start_mock(scenarios=["token_2h_handover"], connection_ttl_seconds=15)`
or `inject(event="fast_forward_timer")` after connect.

**Partial cash-out:** `start_mock(scenarios=["partial_cashout_aggregator"])`, send `0.5` then
`0.8` (accept); `0.3` after `0.5` (reject).

Example agent prompts live under [`prompts/simulator/`](prompts/simulator/) and
[`prompts/build_ticket/`](prompts/build_ticket/).

```bash
uv run pytest src/tests/test_simulator.py
```


---

## Rejection code catalog

The MCP server loads
[`src/mts_client_integration/data/rejection_codes.json`](src/mts_client_integration/data/rejection_codes.json)
at startup. Edit that file to add or update rejection codes, reproduction steps,
and fix suggestions.

Point to a different catalog:

```bash
export MTS_REJECTION_CODES_PATH=/path/to/rejection_codes.json
```

## Ticket 3.0 request models (Python)

```python
from mts_client_integration.models.ticket3 import Request, RequestValidator

request = Request.model_validate(ticket_dict)  # envelope + content parsing
errors = RequestValidator().iter_errors(ticket_dict)  # JSON Schema errors
```

## Regenerating Ticket 3.0 models

When the public Ticket 3.0 request JSON Schema changes, refresh the packaged
schema and generated Pydantic types:

```bash
uv run --with datamodel-code-generator scripts/regenerate_ticket3_models.py
```

By default the script reads
`src/mts_client_integration/models/ticket3/schemas/request.json` and overwrites
`_generated.py`. To import a newer schema file from disk:

```bash
uv run --with datamodel-code-generator scripts/regenerate_ticket3_models.py \
  --schema /path/to/request.json
```

The script:

1. Copies the schema into `schemas/request.json` when `--schema` points elsewhere
2. Runs `datamodel-code-generator` to overwrite `_generated.py`
3. Removes the codegen stub `Model` envelope class (the hand-written `request.py` replaces it)

After regeneration, review these hand-written modules if content types or
operations changed:

| File | Update when… |
|------|----------------|
| `content.py` | New or renamed `content.type` values |
| `operations.py` | New or renamed `operation` values |
| `request.py` | Envelope fields or validation rules change |
| `validator.py` | Validation wiring changes (rare) |

Then run `uv run ruff check src/mts_client_integration/models/ticket3` and
`uv run mypy`.

## Project layout

```text
.
├── pyproject.toml
├── scripts/
│   └── regenerate_ticket3_models.py
├── src/
│   ├── server.py                 # repo-local FastMCP entrypoint shim
│   ├── mts_client_integration/   # installable package
│   │   ├── data/
│   │   │   ├── rejection_codes.json  # MCP lookup catalog shipped in the wheel
│   │   │   └── session_state.md      # session_state input documentation
│   │   ├── tools/
│   │   │   ├── mcp_server.py         # FastMCP server, lifespan, tool registration
│   │   │   ├── lookup_rejection.py   # lookup_rejection_code tool
│   │   │   ├── validate_ticket.py    # validate_ticket_request tool
│   │   │   ├── build_ticket.py       # build_placement / build_cashout / build_ext_settlement
│   │   │   └── mock_server.py        # start_mock / inject / stop_mock / send_to_mock
│   │   ├── services/
│   │   │   ├── catalog.py            # rejection_codes.json loader
│   │   │   ├── validation.py         # orchestrates all four validation layers
│   │   │   ├── business_rules/       # rule registry: engine + envelope/selection/stake/... rules
│   │   │   ├── ack_state_machine.py  # ACK / nACK matrix over the session state
│   │   │   ├── session_state.py      # session_state parsing + prior-state digest
│   │   │   ├── preset_catalog.py     # preset registry queries
│   │   │   ├── preset_docs.py        # agent-facing preset documentation
│   │   │   ├── template_builder.py   # preset + params merge and build
│   │   │   └── simulator/            # WebSocket mock server, handlers, wire client
│   │   │   └── ticket_tree.py        # shared raw-payload traversal helpers
│   │   └── models/
│   │       ├── rejection.py
│   │       ├── validation.py         # ValidationResult (all layers)
│   │       ├── business_rules.py     # rule dataclasses + reference tables
│   │       └── ticket3/              # Ticket 3.0 request models
│   └── tests/
├── prompts/                      # example agent prompts
└── LICENSE
```

## Development

```bash
uv run pre-commit install   # optional
uv run ruff check src scripts
uv run ruff format --check src scripts
uv run mypy
uv run pytest --cov            # fails below the coverage threshold in pyproject.toml
uv run mutmut run              # mutation testing (business rules + ACK state machine; Linux)
```

CI runs these checks, including the mutation score gate, on every pull request
(`.github/workflows/ci.yml`). See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request
expectations.

## License

MIT — see [LICENSE](LICENSE).
