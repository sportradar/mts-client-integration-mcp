"""Tests for rejection catalog and lookup tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mts_client_integration.models.rejection import TicketContext, resolve_operation
from mts_client_integration.services.catalog import RejectionCatalog, normalize_code
from mts_client_integration.tools.lookup_rejection import perform_rejection_lookup


@pytest.mark.parametrize(("raw", "expected"), [(101, -101), (-101, -101)])
def test_normalize_code_is_always_negative(raw: int, expected: int) -> None:
    assert normalize_code(raw) == expected


def test_lookup_normalizes_positive_code(catalog: RejectionCatalog) -> None:
    positive = perform_rejection_lookup(catalog, 101, operation="ticket-cashout")
    negative = perform_rejection_lookup(catalog, -101, operation="ticket-cashout")
    assert positive.found is True
    assert positive.code == -101
    assert positive.message == negative.message


def test_lookup_operation_picks_variant(catalog: RejectionCatalog) -> None:
    placement = perform_rejection_lookup(catalog, -101, operation="ticket-placement")
    cashout = perform_rejection_lookup(catalog, -101, operation="ticket-cashout")
    assert placement.found and cashout.found
    assert placement.message != cashout.message
    assert placement.ambiguous is False


def test_lookup_without_operation_ambiguous_multi_variant(catalog: RejectionCatalog) -> None:
    result = perform_rejection_lookup(catalog, -101)
    placement = perform_rejection_lookup(catalog, -101, operation="ticket-placement")
    cashout = perform_rejection_lookup(catalog, -101, operation="ticket-cashout")
    assert result.found is True
    assert result.ambiguous is True
    assert {"ticket-placement", "ticket-cashout"} <= set(result.operations)
    for variant in (placement.message, cashout.message):
        assert variant is not None
        assert variant in (result.message or "")


def test_lookup_unknown_code(catalog: RejectionCatalog) -> None:
    result = perform_rejection_lookup(catalog, -999999)
    assert result.found is False
    assert result.message is None
    response = result.to_response_dict()
    assert response["found"] is False


@pytest.mark.parametrize(
    ("operation", "context_operation", "expected"),
    [
        pytest.param("ticket-placement", None, "ticket-placement", id="operation-only"),
        pytest.param(None, "ticket-cashout", "ticket-cashout", id="context-only"),
        pytest.param("a", "b", "a", id="operation-wins-over-context"),
        pytest.param(None, None, None, id="neither"),
    ],
)
def test_resolve_operation_precedence(
    operation: str | None, context_operation: str | None, expected: str | None
) -> None:
    context = TicketContext(operation=context_operation) if context_operation else None
    assert resolve_operation(operation=operation, ticket_context=context) == expected


def test_catalog_load_from_env_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = {
        "-42": {
            "code": -42,
            "message": "Test only",
            "operation": "ticket-placement",
        }
    }
    path = tmp_path / "codes.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("MTS_REJECTION_CODES_PATH", str(path))
    catalog = RejectionCatalog.load()
    result = catalog.lookup(-42)
    assert result.found is True
    assert result.message == "Test only"


def test_catalog_bad_entry_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"x": {"code": "not-a-number", "message": "nope"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid rejection catalog entry"):
        RejectionCatalog.load(path)


def test_single_variant_not_ambiguous(catalog: RejectionCatalog) -> None:
    result = perform_rejection_lookup(catalog, -100)
    assert result.found is True
    assert result.ambiguous is False
