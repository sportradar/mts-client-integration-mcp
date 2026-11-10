"""Service-facing helpers for the MCP simulator tools.

Every function takes the ``MockServerManager`` owned by the server lifespan and raises
``MockServerError`` (or ``ValueError`` for invalid input) on failure; the MCP layer
converts those into ``ToolError``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field

from mts_client_integration.services.simulator.catalog import (
    AuthMode,
    InjectEvent,
    RateLimitProfile,
    get_catalog_documentation,
)
from mts_client_integration.services.simulator.client_ops import send_to_running_mock
from mts_client_integration.services.simulator.server import (
    MockConfig,
    MockServerManager,
)
from mts_client_integration.tools._context import app_context
from mts_client_integration.tools._errors import mock_errors


def _list_mock_scenarios() -> dict[str, Any]:
    """Return the closed catalog of scenario IDs, bundles, and inject events."""
    return get_catalog_documentation()


def _start_mock(
    manager: MockServerManager,
    scenarios: list[str] | None = None,
    rate_limit_profile: RateLimitProfile = "integration",
    ws_port: int | None = None,
    oauth_port: int | None = None,
    connection_ttl_seconds: int = 7200,
    auth_mode: AuthMode = "lenient",
    scenario_params: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Start the fixture-driven local MTS WebSocket mock server."""
    config = MockConfig(
        scenarios=list(scenarios) if scenarios is not None else ["realistic_mix"],
        rate_limit_profile=rate_limit_profile,
        ws_port=ws_port,
        oauth_port=oauth_port,
        connection_ttl_seconds=connection_ttl_seconds,
        auth_mode=auth_mode,
        scenario_params=scenario_params,
    )
    return manager.start(config)


def _stop_mock(manager: MockServerManager) -> dict[str, Any]:
    """Stop the running mock server and return wire log + metrics."""
    return manager.stop()


def _inject_mock(
    manager: MockServerManager,
    event: InjectEvent,
    duration_seconds: int | None = None,
) -> dict[str, Any]:
    """Inject a mid-session connectivity or timer event into the running mock."""
    return manager.inject(event, duration_seconds=duration_seconds)


def _mock_status(manager: MockServerManager) -> dict[str, Any]:
    """Poll mock server status without stopping it."""
    return manager.status()


def _send_to_mock(
    manager: MockServerManager,
    payload: dict[str, Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
    *,
    reuse_connection: bool = True,
    timeout_seconds: float = 10.0,
    authorization: str | None = None,
    fetch_oauth_token: bool = False,
) -> dict[str, Any]:
    """Send Ticket 3.0 envelope(s) to the running local mock WebSocket server."""
    return send_to_running_mock(
        manager,
        payload=payload,
        messages=messages,
        reuse_connection=reuse_connection,
        timeout_seconds=timeout_seconds,
        authorization=authorization,
        fetch_oauth_token=fetch_oauth_token,
    )


def register(mcp: FastMCP) -> None:
    @mcp.tool
    def list_mock_scenarios() -> dict[str, object]:
        """List simulator scenario IDs, bundles, and inject events.

        Use before ``start_mock`` to discover valid ``scenarios`` values and
        ``inject`` event names. Scenarios are a closed catalog aligned with
        client integration scenarios (connectivity, frame split, rate limit, alt-stake,
        cancellation ACK matrix, partial cashout).
        """
        return _list_mock_scenarios()

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
            RateLimitProfile,
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
        auth_mode: AuthMode = "lenient",
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
        with mock_errors():
            return _start_mock(
                app_context(ctx).mock_manager,
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
            InjectEvent,
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
        with mock_errors():
            return _inject_mock(
                app_context(ctx).mock_manager, event, duration_seconds=duration_seconds
            )

    @mcp.tool
    def stop_mock(ctx: Context) -> dict[str, object]:
        """Stop the mock server and return wire log plus session metrics.

        The ``wire_log`` list is compatible with ``validate_ticket_request``
        ``session_state`` input for ACK / nACK verification.
        """
        with mock_errors():
            return _stop_mock(app_context(ctx).mock_manager)

    @mcp.tool
    def mock_status(ctx: Context) -> dict[str, object]:
        """Poll the running mock server without stopping it."""
        return _mock_status(app_context(ctx).mock_manager)

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
        with mock_errors():
            return _send_to_mock(
                app_context(ctx).mock_manager,
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
        return _list_mock_scenarios()


list_mock_scenarios = _list_mock_scenarios
start_mock = _start_mock
stop_mock = _stop_mock
inject_mock = _inject_mock
mock_status = _mock_status
send_to_mock = _send_to_mock
