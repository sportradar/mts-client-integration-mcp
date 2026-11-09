"""Markdown documents shipped as package data and served as MCP resources."""

from __future__ import annotations

from functools import cache
from importlib.resources import files

_DATA_PACKAGE = "mts_client_integration.data"


@cache
def _read_data_text(name: str) -> str:
    return files(_DATA_PACKAGE).joinpath(name).read_text(encoding="utf-8")


def session_state_documentation() -> str:
    """Describe the ``session_state`` input shape for ``validate_ticket_request``."""
    return _read_data_text("session_state.md")
