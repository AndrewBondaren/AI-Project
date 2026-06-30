"""T2 section import — validate via facade before persist."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import HTTPException

from app.application.worldData.jsonValidation import format_validation_issues
from app.application.worldData.jsonValidation.sectionImport import (
    SECTIONS_REQUIRING_SEED,
    validate_section_import,
)
from app.application.worldData.jsonValidation.types import SectionKey


async def gate_section_import(
    container,
    *,
    world_uid: str,
    section: SectionKey,
    payload: list[Any] | dict[str, Any],
) -> None:
    """Load world (+ seed when needed), run SECTION validation, raise 422 on failure."""
    world = asdict(await container.world_service().get_by_id(world_uid))
    seed_snapshot = None
    if section in SECTIONS_REQUIRING_SEED:
        seed_snapshot = await container.seed_service().export_all()
    validation = await validate_section_import(
        container.json_validation_facade(),
        world=world,
        section=section,
        payload=payload,
        world_uid=world_uid,
        seed_snapshot=seed_snapshot,
    )
    if not validation.ok:
        raise HTTPException(
            status_code=422,
            detail=format_validation_issues(validation),
        )
