"""T6 seed import — validate via facade before persist."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.application.worldData.jsonValidation import format_validation_issues
from app.application.worldData.jsonValidation.seedImport import (
    validate_seed_import,
    validate_seed_row,
)


async def gate_seed_import(container, payload: dict[str, Any]) -> None:
    validation = await validate_seed_import(
        container.json_validation_facade(),
        payload,
    )
    if not validation.ok:
        raise HTTPException(
            status_code=422,
            detail=format_validation_issues(validation),
        )


async def gate_seed_upsert(container, table: str, row: dict[str, Any]) -> None:
    validation = await validate_seed_row(
        container.json_validation_facade(),
        table,
        row,
    )
    if not validation.ok:
        raise HTTPException(
            status_code=422,
            detail=format_validation_issues(validation),
        )
