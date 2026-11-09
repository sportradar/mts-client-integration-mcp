"""Load and query the MTS rejection code catalog."""

from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path
from typing import Any

from mts_client_integration.models.rejection import (
    RejectionCodeRecord,
    RejectionLookupResult,
    RejectionVariant,
)

_CATALOG_PACKAGE = "mts_client_integration.data"
_CATALOG_NAME = "rejection_codes.json"


class RejectionCatalog:
    """In-memory lookup table for MTS rejection codes."""

    def __init__(self, entries: dict[int, RejectionCodeRecord]) -> None:
        self._entries = entries

    @classmethod
    def load(cls, path: Path | None = None) -> RejectionCatalog:
        raw = json.loads(_read_catalog_text(path))
        entries: dict[int, RejectionCodeRecord] = {}
        for key, value in raw.items():
            try:
                entries[int(key)] = _parse_record(value)
            except (KeyError, TypeError, ValueError) as exc:
                msg = f"Invalid rejection catalog entry {key!r}: {exc!r}"
                raise ValueError(msg) from exc
        return cls(entries)

    def lookup(
        self,
        code: int,
        *,
        operation: str | None = None,
    ) -> RejectionLookupResult:
        normalized = normalize_code(code)
        record = self._entries.get(normalized)
        if record is None or not record.variants:
            return RejectionLookupResult(
                code=normalized,
                message=None,
                found=False,
            )

        guidance = _guidance_from_record(record)

        if operation is not None:
            for variant in record.variants:
                if operation in variant.operations:
                    return RejectionLookupResult(
                        code=record.code,
                        message=variant.message,
                        found=True,
                        operations=variant.operations,
                        category=variant.category,
                        ambiguous=False,
                        **guidance,
                    )

        if len(record.variants) == 1:
            variant = record.variants[0]
            return RejectionLookupResult(
                code=record.code,
                message=variant.message,
                found=True,
                operations=variant.operations,
                category=variant.category,
                ambiguous=False,
                **guidance,
            )

        labeled_messages = [
            f"[{', '.join(variant.operations)}] {variant.message}" for variant in record.variants
        ]
        all_operations = tuple(
            operation_name for variant in record.variants for operation_name in variant.operations
        )
        return RejectionLookupResult(
            code=record.code,
            message=" | ".join(labeled_messages),
            found=True,
            operations=all_operations,
            category=record.variants[0].category,
            ambiguous=True,
            **guidance,
        )


def _parse_variant(raw: dict[str, Any]) -> RejectionVariant:
    return RejectionVariant(
        message=str(raw["message"]),
        category=raw.get("category"),
        operations=tuple(str(item) for item in raw.get("operations", [])),
    )


def _parse_record(value: dict[str, Any]) -> RejectionCodeRecord:
    variants: tuple[RejectionVariant, ...]
    variants_raw = value.get("variants")
    if variants_raw is None:
        operations_raw = value.get("operations")
        if operations_raw is None and "operation" in value:
            operations_raw = [value["operation"]]
        variants = (
            RejectionVariant(
                message=str(value["message"]),
                category=value.get("category"),
                operations=tuple(str(item) for item in (operations_raw or [])),
            ),
        )
    else:
        variants = tuple(_parse_variant(variant) for variant in variants_raw)
    return RejectionCodeRecord(
        code=int(value["code"]),
        variants=variants,
        steps_to_reproduce=_parse_string_list(value.get("steps_to_reproduce")),
        fix_suggestions=_parse_string_list(value.get("fix_suggestions")),
    )


def _read_catalog_text(path: Path | None) -> str:
    """Read the rejection catalog from an explicit path, env override, or package data."""
    if path is not None:
        return _read_path(path)
    configured = os.getenv("MTS_REJECTION_CODES_PATH")
    if configured:
        return _read_path(Path(configured).expanduser())
    try:
        return files(_CATALOG_PACKAGE).joinpath(_CATALOG_NAME).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "Rejection catalog not found in the installed package "
            f"({_CATALOG_PACKAGE}/{_CATALOG_NAME}). "
            "Set MTS_REJECTION_CODES_PATH to a catalog file."
        ) from exc


def _read_path(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(
            f"Rejection catalog not found at {path}. "
            "Set MTS_REJECTION_CODES_PATH to a catalog file."
        )
    return path.read_text(encoding="utf-8")


def normalize_code(code: int) -> int:
    if code > 0:
        return -code
    return code


def _parse_string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _guidance_from_record(record: RejectionCodeRecord) -> dict[str, tuple[str, ...]]:
    return {
        "steps_to_reproduce": record.steps_to_reproduce,
        "fix_suggestions": record.fix_suggestions,
    }
