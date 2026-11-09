"""FastMCP server for MTS client integration tools."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import Annotated, Literal

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from mts_client_integration.models.rejection import TicketContext
from mts_client_integration.models.templates import (
    BuildResult,
    CashoutBuildParams,
    ExtSettlementBuildParams,
    PlacementBuildParams,
    PresetUnavailableError,
)
from mts_client_integration.models.ticket3.validator import (
    load_request_schema,
    load_response_schema,
)
from mts_client_integration.services import preset_catalog, preset_docs
from mts_client_integration.services.catalog import RejectionCatalog
from mts_client_integration.services.data_docs import session_state_documentation
from mts_client_integration.services.integration_context import (
    ENVELOPE_CONTEXT_DOC,
    get_envelope_context_documentation,
)
from mts_client_integration.services.simulator.server import MockServerError, MockServerManager
from mts_client_integration.tools import build_ticket as build_tools
from mts_client_integration.tools import mock_server as mock_tools
from mts_client_integration.tools.lookup_rejection import lookup_rejection_code as lookup_rejection
from mts_client_integration.tools.validate_ticket import (
    validate_ticket_request as run_validate_ticket_request,
)

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    catalog: RejectionCatalog
    mock_manager: MockServerManager


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    app_context = AppContext(catalog=RejectionCatalog.load(), mock_manager=MockServerManager())
    try:
        yield app_context
    finally:
        if app_context.mock_manager.is_running:
            try:
                app_context.mock_manager.stop()
            except MockServerError:
                logger.exception("Failed to stop mock server during shutdown")


def _app_context(ctx: Context) -> AppContext:
    request_context = ctx.request_context
    if request_context is None:
        raise ToolError("MCP request context is unavailable")
    app_context: AppContext = request_context.lifespan_context
    return app_context


def _run_build(shape: str, build: Callable[[], BuildResult]) -> dict[str, object]:
    """Run a preset build and convert expected failures into actionable ``ToolError``s."""
    try:
        result = build()
    except PresetUnavailableError as exc:
        raise ToolError(exc.describe()) from exc
    except ValueError as exc:
        raise ToolError(
            f"{exc}. See mts://templates/{shape} for required fields and example."
        ) from exc
    return result.to_response_dict()


@contextmanager
def _mock_errors() -> Iterator[None]:
    """Convert simulator failures into ``ToolError`` so MCP clients see ``isError``."""
    try:
        yield
    except (MockServerError, ValueError) as exc:
        raise ToolError(str(exc)) from exc


def create_server() -> FastMCP:
    mcp = FastMCP("MTS Client Integration", lifespan=lifespan)

    @mcp.tool
    def lookup_rejection_code(
        code: int,
        ctx: Context,
        ticket_context: TicketContext | None = None,
        operation: str | None = None,
    ) -> dict[str, object]:
        """Look up the MTS rejection message for a validation or response code.

        Use when an integrator received a numeric rejection code from MTS and
        needs the canonical message text. When the catalog entry includes them,
        also returns ``steps_to_reproduce`` and ``fix_suggestions``.

        When the same code means different things for different request types,
        pass context from the rejected request so the correct message is returned.

        **How to fill ``ticket_context``**

        1. Find the Ticket 3.0 request JSON that MTS rejected (your outbound
           message, not the response).
        2. Copy its top-level ``operation`` value into ``ticket_context``.
        3. Call with e.g. ``ticket_context={"operation": "ticket-placement"}`` for
           a placement rejection, or ``ticket_context={"operation": "cashout-build"}``
           when disambiguating codes shared across operation families.

        Do not send the full request envelope unless that is all you have — only
        ``operation`` is read today. Additional ``ticket_context`` fields may be
        added later for root-cause hints.

        **Shortcut:** pass the same value as ``operation="ticket-placement"`` (or
        another operation string) when you do not need a structured context object.

        If neither ``ticket_context.operation`` nor ``operation`` is provided and
        the code has multiple meanings, the result includes all variants with
        ``ambiguous: true``; retry with the operation from your request.
        """

        result = lookup_rejection(
            _app_context(ctx).catalog,
            code,
            operation=operation,
            ticket_context=ticket_context,
        )
        return result.to_response_dict()

    @mcp.tool
    def build_placement(
        shape: Annotated[
            str,
            Field(
                description=(
                    "Placement preset id. Call list_ticket_shapes() or read "
                    "mts://templates/{shape} for the full contract and example."
                ),
                json_schema_extra={"enum": preset_catalog.preset_ids_for_builder("placement")},
            ),
        ],
        params: PlacementBuildParams,
    ) -> dict[str, object]:
        """Build a ``ticket-placement`` envelope from a named preset.

        **All business fields are required** in ``params`` (operator_id, limit_id,
        channel, stake, currency, selections or bets, etc.). The preset only fills
        shape facts such as ``bet_type`` and ``size``. Nothing is invented: never
        guess operator_id, limit_id, odds, or stake — ask the integrator.

        Read ``mts://templates/{shape}`` first for ``required_params``, JSON Schema,
        ``how_to_set_fields``, and a full copy-paste ``example_params``.

        Returns ``shape``, ``operation``, and ``payload``. Call ``validate_ticket_request``
        on ``payload`` for schema and business rules.
        """
        return _run_build(shape, lambda: build_tools.build_placement(shape, params))

    @mcp.tool
    def build_cashout(
        shape: Annotated[
            str,
            Field(
                description=(
                    "Cashout preset id. Call list_ticket_shapes() or read mts://templates/{shape}."
                ),
                json_schema_extra={"enum": preset_catalog.preset_ids_for_builder("cashout")},
            ),
        ],
        params: CashoutBuildParams,
    ) -> dict[str, object]:
        """Build a ``ticket-cashout`` envelope from a named preset.

        Requires ``operator_id``, ``currency``, ``code`` (0..1000), ``ticket_id``,
        ``ticket_signature``, ``payout_amount``, and for partial cashouts the
        **cumulative** ``percentage`` in (0, 1). Do not invent these — ask the integrator.

        Read ``mts://templates/{shape}`` for the full example.
        """
        return _run_build(shape, lambda: build_tools.build_cashout(shape, params))

    @mcp.tool
    def build_ext_settlement(
        shape: Annotated[
            str,
            Field(
                description=(
                    "External-settlement preset id. Call list_ticket_shapes() or read "
                    "mts://templates/{shape}."
                ),
                json_schema_extra={"enum": preset_catalog.preset_ids_for_builder("ext_settlement")},
            ),
        ],
        params: ExtSettlementBuildParams,
    ) -> dict[str, object]:
        """Build a ``ticket-ext-settlement`` envelope from a named preset.

        Requires ``operator_id``, ``currency``, ticket ids, signature, and payout.
        Bet-level settlement requires ``bet_id``. Read ``mts://templates/{shape}`` for the example.
        """
        return _run_build(shape, lambda: build_tools.build_ext_settlement(shape, params))

    @mcp.tool
    def list_ticket_shapes(
        include_planned: bool = False,
    ) -> dict[str, object]:
        """List golden-ticket shape presets and their availability status.

        Use to discover valid ``shape`` values for ``build_placement``, ``build_cashout``,
        and ``build_ext_settlement``. Shapes with
        ``status: available`` can be built today; ``planned`` shapes are documented
        aliases awaiting E2E canonical JSON.
        """
        presets = preset_catalog.list_shapes(include_planned=include_planned)
        return {
            "shapes": [preset_docs.preset_to_resource_dict(p) for p in presets],
            "count": len(presets),
        }

    @mcp.tool
    def validate_ticket_request(
        payload: dict[str, object] | str,
        operation: str | None = None,
        session_state: list[dict[str, object]] | str | None = None,
        reference_time_utc_ms: int | None = None,
        serialized_bytes: int | None = None,
    ) -> dict[str, object]:
        """Validate a Ticket 3.0 request payload before sending it to MTS.

        For outbound **request** envelopes only — not for MTS reply/response
        validation. Do not pass inbound ``*-reply`` messages as ``payload``;
        use ``mts://schemas/ticket3/response`` to inspect response shape.

        Use when building or reviewing outbound Ticket 3.0 JSON to catch,
        locally, the issues that otherwise surface as MTS rejections
        (``-1xx``/``-2xx``/``-3xx``). Runs four layers in one pass:

        1. **Schema** — JSON Schema validation (shape / required fields).
        2. **Envelope** — typed parse + ``operation`` ↔ ``content.type`` check.
        3. **Business rules** — selection cap (100), positive stake, min odds
           (1.01), currency format, system ``size`` validity + predefined
           permutations (Trixie/Yankee/…), ways same-event, non-SR-in-system and
           banker-on-non-SR, Custom Bet anti-multiplication + caps, cumulative
           partial cash-out percentage,
           channel/language expectations, frame-size (32 KB x 4), and more.
        4. **ACK / nACK state machine** — the cancellation ACK matrix and the
           ticket-placement acknowledgement flow (``ticket-reply`` ->
           ``ticket-ack``/nACK), derived from ``session_state``.

        ## How to construct the input

        Direction is always from the integrator's (client's) point of view:
        *outbound* = client → MTS (requests and ACKs); *inbound* = MTS → client
        (responses, whose ``content.type`` ends in ``-reply``).

        **payload** — the single outbound request envelope you are about to
        send, verbatim as it goes over the WebSocket::

            {"operatorId": "...", "content": {...}, "correlationId": "...",
             "timestampUtc": 1745311871018, "operation": "...", "version": "3.0"}

        Pass exactly one message here: the one being validated. Do NOT include
        earlier messages — those belong in ``session_state``.

        **operation** — optional; when given it must match ``payload.operation``.

        **session_state** — the messages already exchanged for this ticket in
        the current session, in chronological order, EXCLUDING ``payload``. It
        supplies the history needed for stateful business rules (cumulative
        cash-out percentage, monotonic factor, placement currency) and the ACK /
        nACK flow. Omit it for a first, stateless placement. Two forms:

        - a structured list of ``{"direction": "outbound" | "inbound",
          "message": {<envelope>}}`` entries (``direction`` is optional and
          inferred: an envelope with ``operatorId`` or a non-``*-reply``
          ``content.type`` is outbound, a ``*-reply`` is inbound), or
        - a raw pasted log dump (string) with ``->``/``<-`` (or
          ``request:``/``response:``) markers.

        Messages are paired by ``correlationId``; ACKs match by
        ``cancellationId`` / ``cashoutId`` (falling back to ``ticketId``).

        Example — a follow-up partial cash-out. Send the new ``ticket-cashout``
        as ``payload`` and put the placement + earlier cash-out(s) in
        ``session_state``::

            payload = {new ticket-cashout envelope}
            session_state = [
              {"direction": "outbound", "message": {ticket-placement envelope}},
              {"direction": "outbound", "message": {prior ticket-cashout envelope}},
            ]

        See the ``mts://schemas/session-state`` MCP resource for the full shape.

        **reference_time_utc_ms** — clock for ``timestampUtc`` checks; defaults
        to now.

        **serialized_bytes** — byte length of the serialized message for the
        frame-size rule; defaults to the encoded ``payload`` size.

        Returns ``schema_ok`` / ``envelope_ok`` / ``business_rules_ok`` /
        ``ack_state_machine_ok`` booleans plus structured issue lists. Each
        business rule / ACK issue carries a ``severity`` (``error`` / ``warning``
        / ``info``); only ``error`` flips the matching ``*_ok`` flag. Messages in
        ``session_state`` that cannot be parsed or paired appear in
        ``session_state_errors``.
        """
        result = run_validate_ticket_request(
            payload,
            operation=operation,
            session_state=session_state,
            reference_time_utc_ms=reference_time_utc_ms,
            serialized_bytes=serialized_bytes,
        )
        return result.to_response_dict()

    @mcp.tool
    def list_mock_scenarios() -> dict[str, object]:
        """List simulator scenario IDs, bundles, and inject events.

        Use before ``start_mock`` to discover valid ``scenarios`` values and
        ``inject`` event names. Scenarios are a closed catalog aligned with
        client integration scenarios (connectivity, frame split, rate limit, alt-stake,
        cancellation ACK matrix, partial cashout).
        """
        return mock_tools.list_mock_scenarios()

    @mcp.tool
    def start_mock(
        ctx: Context,
        scenarios: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Scenario leaf IDs and/or bundle IDs. Default realistic_mix. "
                    "Call list_mock_scenarios() for the catalog."
                ),
            ),
        ] = None,
        rate_limit_profile: Annotated[
            Literal["integration", "production"],
            Field(
                description=(
                    "Wire rate limit only: integration=10 r/s, production=500 r/s. "
                    "Not related to ticket builder tools."
                ),
            ),
        ] = "integration",
        ws_port: int | None = None,
        oauth_port: int | None = None,
        connection_ttl_seconds: int = 7200,
        auth_mode: Literal["lenient", "strict"] = "lenient",
        scenario_params: dict[str, dict[str, object]] | None = None,
    ) -> dict[str, object]:
        """Start the fixture-driven local MTS WebSocket mock server.

        Boots a background WS server (and stub OAuth token endpoint). Point your
        MTS client at the returned ``ws_url``. Use ``inject`` for
        ``connection_blocked`` / ``force_disconnect`` / ``fast_forward_timer``.
        Call ``stop_mock`` when done; pass ``wire_log`` to ``validate_ticket_request``.

        **Examples**

        - Smoke test: ``scenarios=["realistic_mix"]`` (default)
        - Token handover / reconnect: ``scenarios=["token_2h_handover"]``,
          ``connection_ttl_seconds=15``
        - Connection blocked: ``inject(event="connection_blocked")``
        - Cancellation ACK matrix: ``scenarios=["cancellation_matrix"]``
        """
        with _mock_errors():
            return mock_tools.start_mock(
                _app_context(ctx).mock_manager,
                scenarios=scenarios,
                rate_limit_profile=rate_limit_profile,
                ws_port=ws_port,
                oauth_port=oauth_port,
                connection_ttl_seconds=connection_ttl_seconds,
                auth_mode=auth_mode,
                scenario_params=scenario_params,
            )

    @mcp.tool
    def inject(
        ctx: Context,
        event: Annotated[
            Literal[
                "connection_blocked",
                "connection_unblocked",
                "force_disconnect",
                "fast_forward_timer",
            ],
            Field(description="Mid-session connectivity or timer inject event."),
        ],
        duration_seconds: int | None = None,
    ) -> dict[str, object]:
        """Inject a connectivity or timer event into the running mock server.

        Use for connection blocked / unblocked (``connection_blocked`` /
        ``connection_unblocked``) and to shortcut token handover
        (``fast_forward_timer``). Requires ``start_mock``
        to be running.
        """
        with _mock_errors():
            return mock_tools.inject_mock(
                _app_context(ctx).mock_manager, event, duration_seconds=duration_seconds
            )

    @mcp.tool
    def stop_mock(ctx: Context) -> dict[str, object]:
        """Stop the mock server and return wire log plus session metrics.

        The ``wire_log`` list is compatible with ``validate_ticket_request``
        ``session_state`` input for ACK / nACK verification.
        """
        with _mock_errors():
            return mock_tools.stop_mock(_app_context(ctx).mock_manager)

    @mcp.tool
    def mock_status(ctx: Context) -> dict[str, object]:
        """Poll the running mock server without stopping it."""
        return mock_tools.mock_status(_app_context(ctx).mock_manager)

    @mcp.tool
    def send_to_mock(
        ctx: Context,
        payload: dict[str, object] | None = None,
        messages: list[dict[str, object]] | None = None,
        reuse_connection: Annotated[
            bool,
            Field(
                description=(
                    "When true (default), send all messages on one WebSocket "
                    "connection. Use for alt-stake resubmit flows."
                ),
            ),
        ] = True,
        timeout_seconds: Annotated[
            float,
            Field(description="Seconds to wait for each mock reply."),
        ] = 10.0,
        authorization: Annotated[
            str | None,
            Field(description="Optional Authorization header (Bearer token)."),
        ] = None,
        fetch_oauth_token: Annotated[
            bool,
            Field(
                description=(
                    "When true, fetch a Bearer token from the mock oauth_url "
                    "before connecting (for auth_mode strict)."
                ),
            ),
        ] = False,
    ) -> dict[str, object]:
        """Send Ticket 3.0 traffic to the running local mock server.

        Requires ``start_mock`` to be running; traffic is only ever sent to that local mock.
        Build envelopes with ``build_placement`` / ``build_cashout`` / ``build_ext_settlement``
        or pass hand-written JSON.

        **Examples**

        - Single placement::

            send_to_mock(payload=<build_placement result payload>)

        - Alt-stake resubmit on one connection::

            send_to_mock(messages=[first_placement, resubmit_with_ref])

        - Partial cashout sequence (new connection per message)::

            send_to_mock(messages=[co_0_5, co_0_3, co_0_8], reuse_connection=False)

        Returns ``exchanges`` (sent + reply pairs) and any connection close code.
        Call ``stop_mock`` when done to retrieve the full ``wire_log``.
        """
        with _mock_errors():
            return mock_tools.send_to_mock(
                _app_context(ctx).mock_manager,
                payload=payload,
                messages=messages,
                reuse_connection=reuse_connection,
                timeout_seconds=timeout_seconds,
                authorization=authorization,
                fetch_oauth_token=fetch_oauth_token,
            )

    @mcp.resource("mts://simulator/scenarios")
    def simulator_scenarios() -> dict[str, object]:
        """Scenario catalog for the targeted local simulator."""
        return mock_tools.list_mock_scenarios()

    @mcp.resource("mts://schemas/session-state")
    def session_state_schema() -> str:
        """Describe the ``session_state`` input shape for ``validate_ticket_request``."""
        return session_state_documentation()

    @mcp.resource("mts://schemas/ticket3/request")
    def ticket3_request_schema() -> dict[str, object]:
        """External Ticket 3.0 request JSON Schema (outbound client → MTS envelopes)."""
        return load_request_schema()

    @mcp.resource("mts://schemas/ticket3/response")
    def ticket3_response_schema() -> dict[str, object]:
        """External Ticket 3.0 reply/response JSON Schema (inbound MTS → client envelopes)."""
        return load_response_schema()

    @mcp.resource("mts://templates/builder-schema")
    def ticket_builder_schema() -> dict[str, object]:
        """JSON Schemas for placement, cashout, and ext-settlement build params."""
        return preset_docs.get_builder_schema_documentation()

    @mcp.resource("mts://templates/{shape}")
    def ticket_template_preset(shape: str) -> dict[str, object]:
        """Preset metadata and example params for a named bet shape."""
        try:
            preset = preset_catalog.get_preset(shape)
        except KeyError:
            return preset_catalog.preset_unavailable_response(shape)
        if preset.status != "available":
            return preset_catalog.preset_unavailable_response(shape)
        return {"found": True, **preset_docs.describe_shape(shape)}

    @mcp.resource("mts://integration/envelope-context")
    def envelope_context() -> dict[str, object]:
        """Production-readiness contract for operatorId, limitId, and channel."""
        return get_envelope_context_documentation()

    @mcp.resource("mts://integration/envelope-context.md")
    def envelope_context_markdown() -> str:
        """Markdown guide for integrator envelope fields and builder workflow."""
        return ENVELOPE_CONTEXT_DOC

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
