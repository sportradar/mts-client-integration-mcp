"""Tests for rejection catalog and lookup tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mts_client_integration.models.rejection import TicketContext, resolve_operation
from mts_client_integration.services.catalog import RejectionCatalog, normalize_code
from mts_client_integration.tools.lookup_rejection import perform_rejection_lookup


@pytest.fixture
def catalog() -> RejectionCatalog:
    return RejectionCatalog.load()


def test_normalize_code_positive_becomes_negative() -> None:
    assert normalize_code(101) == -101
    assert normalize_code(-101) == -101


def test_lookup_normalizes_positive_code(catalog: RejectionCatalog) -> None:
    via_catalog = catalog.lookup(101, operation="ticket-cashout")
    via_tool = perform_rejection_lookup(catalog, 101, operation="ticket-cashout")
    assert via_catalog.code == -101
    assert via_tool.code == -101
    assert via_tool.found is True
    assert "bookmaker" in (via_tool.message or "").lower()


def test_lookup_operation_picks_variant(catalog: RejectionCatalog) -> None:
    placement = perform_rejection_lookup(catalog, -101, operation="ticket-placement")
    cashout = perform_rejection_lookup(catalog, -101, operation="ticket-cashout")
    assert placement.found and cashout.found
    assert placement.message != cashout.message
    assert placement.ambiguous is False


def test_lookup_without_operation_ambiguous_multi_variant(catalog: RejectionCatalog) -> None:
    result = perform_rejection_lookup(catalog, -101)
    assert result.found is True
    assert result.ambiguous is True
    assert "|" in (result.message or "")


def test_lookup_unknown_code(catalog: RejectionCatalog) -> None:
    result = perform_rejection_lookup(catalog, -999999)
    assert result.found is False
    assert result.message is None
    response = result.to_response_dict()
    assert response["found"] is False


def test_resolve_operation_precedence() -> None:
    assert (
        resolve_operation(operation="ticket-placement", ticket_context=None) == "ticket-placement"
    )
    assert (
        resolve_operation(
            operation=None,
            ticket_context=TicketContext(operation="ticket-cashout"),
        )
        == "ticket-cashout"
    )
    assert resolve_operation(operation="a", ticket_context=TicketContext(operation="b")) == "a"


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
