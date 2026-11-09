"""Envelope-level rules: timestamp freshness and WebSocket frame size."""

from __future__ import annotations

import json

from mts_client_integration.models.business_rules import (
    MAX_FRAME_BYTES,
    MAX_FRAMES,
    MAX_MESSAGE_BYTES,
    BusinessRuleIssue,
)
from mts_client_integration.services.business_rules.inputs import EnvelopeRuleInput

# Heuristic staleness window; the exact -310 threshold is not published, so this
# rule is emitted as a warning only. See plan "Information gaps".
STALE_THRESHOLD_MS = 60 * 60 * 1000
FUTURE_TOLERANCE_MS = 5 * 1000


def check_timestamp(ctx: EnvelopeRuleInput) -> list[BusinessRuleIssue]:
    reference = ctx.reference_time_utc_ms
    ts = ctx.payload.get("timestampUtc")
    if not isinstance(ts, int) or isinstance(ts, bool):
        return []
    issues: list[BusinessRuleIssue] = []
    if ts > reference + FUTURE_TOLERANCE_MS:
        issues.append(
            BusinessRuleIssue(
                "timestamp_not_future",
                "error",
                "$.timestampUtc",
                f"timestampUtc {ts} is in the future relative to reference {reference}.",
                maps_to_code=-309,
            )
        )
    elif ts < reference - STALE_THRESHOLD_MS:
        issues.append(
            BusinessRuleIssue(
                "timestamp_not_stale",
                "warning",
                "$.timestampUtc",
                (
                    f"timestampUtc {ts} is older than the heuristic staleness "
                    f"window ({STALE_THRESHOLD_MS} ms); MTS may reject as outdated (-310)."
                ),
                maps_to_code=-310,
            )
        )
    return issues


def check_frame_size(ctx: EnvelopeRuleInput) -> list[BusinessRuleIssue]:
    size = ctx.serialized_bytes
    if size is None:
        size = len(json.dumps(ctx.payload, separators=(",", ":")).encode("utf-8"))
    if size > MAX_MESSAGE_BYTES:
        return [
            BusinessRuleIssue(
                "frame_size_limit",
                "error",
                "$",
                (
                    f"Serialized message is {size} bytes, above the {MAX_MESSAGE_BYTES}"
                    f"-byte cap ({MAX_FRAMES} frames x {MAX_FRAME_BYTES} bytes); MTS "
                    "closes the connection with code 1009."
                ),
                maps_to_code=-900,
            )
        ]
    if size > MAX_FRAME_BYTES:
        return [
            BusinessRuleIssue(
                "frame_size_limit",
                "info",
                "$",
                (
                    f"Serialized message is {size} bytes (> {MAX_FRAME_BYTES}); it must "
                    f"be split into at most {MAX_FRAMES} WebSocket frames of "
                    f"{MAX_FRAME_BYTES} bytes each."
                ),
            )
        ]
    return []
