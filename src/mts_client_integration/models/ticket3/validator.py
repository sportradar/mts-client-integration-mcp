"""JSON Schema validation for Ticket 3.0 requests."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft201909Validator
from jsonschema.exceptions import ValidationError


def load_request_schema() -> dict[str, Any]:
    schema_path = files("mts_client_integration.models.ticket3.schemas").joinpath("request.json")
    schema_text = schema_path.read_text(encoding="utf-8")
    return cast(dict[str, Any], json.loads(schema_text))


def _error_sort_key(error: ValidationError) -> list[tuple[int, int, str]]:
    """Sort key that orders mixed ``int``/``str`` path segments without ``TypeError``."""
    return [
        (0, segment, "") if isinstance(segment, int) else (1, 0, str(segment))
        for segment in error.absolute_path
    ]


class RequestValidator:
    """Validates Ticket 3.0 request JSON against the merged request schema."""

    def __init__(self, schema: dict[str, Any] | None = None) -> None:
        self._schema = schema if schema is not None else load_request_schema()
        self._validator = Draft201909Validator(self._schema)  # TODO format checker?

    @property
    def schema(self) -> dict[str, Any]:
        return self._schema

    def iter_errors(self, instance: Any) -> list[ValidationError]:
        return sorted(self._validator.iter_errors(instance), key=_error_sort_key)


def load_response_schema() -> dict[str, Any]:
    schema_path = files("mts_client_integration.models.ticket3.schemas").joinpath("response.json")
    schema_text = schema_path.read_text(encoding="utf-8")
    return cast(dict[str, Any], json.loads(schema_text))
