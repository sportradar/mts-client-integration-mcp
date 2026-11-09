"""Tests for integration envelope documentation helpers."""

from __future__ import annotations

from typing import Any, cast

from mts_client_integration.services.integration_context import (
    ENVELOPE_CONTEXT_DOC,
    get_envelope_context_documentation,
)


def test_envelope_doc_and_structured_metadata_present() -> None:
    assert "build_placement" in ENVELOPE_CONTEXT_DOC
    doc = cast(dict[str, Any], get_envelope_context_documentation())
    assert doc["builder_tools"]["placement"] == "build_placement"
    pairs = cast(list[dict[str, Any]], doc["example_operator_limit_pairs"])
    assert any(p["operator_id"] == "9985" for p in pairs)
