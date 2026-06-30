"""Seed import validation (T6) — docs/tz_json_validation.md."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.types import (
    ValidationKind,
    ValidationRequest,
    ValidationResult,
)


async def validate_seed_import(
    facade: JsonValidationFacade,
    payload: dict[str, list[dict]],
) -> ValidationResult:
    return await facade.validate(ValidationRequest(
        kind=ValidationKind.SEED,
        payload=payload,
    ))


async def validate_seed_row(
    facade: JsonValidationFacade,
    table: str,
    row: dict[str, Any],
) -> ValidationResult:
    return await facade.validate(ValidationRequest(
        kind=ValidationKind.SEED,
        payload={table: [row]},
    ))
