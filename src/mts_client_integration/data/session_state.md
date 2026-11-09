# validate_ticket_request `session_state` input

`session_state` is the ordered history of wire messages already exchanged with
MTS for the current ticket/session, EXCLUDING the `payload` you are validating.
It supplies the context for stateful business rules (cumulative cash-out
percentage, monotonic factors, placement currency) and the ACK / nACK state
machine.

Direction is always from the integrator's (client's) point of view:
- `outbound` — client → MTS (requests and ACKs)
- `inbound` — MTS → client (responses; `content.type` ends in `-reply`)

## Two accepted forms

1. **Structured list** of entries:

   ```json
   [
     {"direction": "outbound", "message": { <full Ticket 3.0 request envelope> }},
     {"direction": "inbound",  "message": { <full Ticket 3.0 response envelope> }}
   ]
   ```

   - `message` is the verbatim envelope, exactly as logged
     (`{ operatorId?, content, correlationId, timestampUtc, operation, version }`).
   - `direction` is optional and inferred when omitted: a message with
     `operatorId` (or a non-`*-reply` `content.type`) is `outbound`; a message
     whose `content.type` ends in `-reply` is `inbound`.

2. **Raw log paste** (a single string). Embedded JSON envelopes are extracted;
   direction is inferred from `->` / `request:` (outbound) and `<-` /
   `response:` (inbound) markers on the same line.

## Pairing

Messages are joined by `correlationId` (request ↔ response). The cancellation
code (101/103/104/105/301/302) is recovered from the outbound `ticket-cancel`
request; the response supplies `status`, `code`, and `signature`. ACKs are
matched by `cancellationId` / `cashoutId` (falling back to `ticketId`).

Inbound responses whose `correlationId` has no matching outbound request are
reported in `session_state_errors` (the output list of session_state
parse/pairing problems).
