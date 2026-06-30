"""T3–T5 CRUD — validate via facade before persist."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import HTTPException

from app.application.worldData.jsonValidation import format_validation_issues
from app.application.worldData.jsonValidation.crudPatch import (
    merge_shallow_patch,
    validate_entity_row,
    validate_world_create,
    validate_world_update,
)
from app.application.worldData.jsonValidation.sectionImport import SECTIONS_REQUIRING_SEED
from app.application.worldData.jsonValidation.types import SectionKey


def _raise_on_fail(validation) -> None:
    if not validation.ok:
        raise HTTPException(
            status_code=422,
            detail=format_validation_issues(validation),
        )


async def gate_world_create(container, data: dict[str, Any]) -> dict[str, Any]:
    facade = container.json_validation_facade()
    validation = await validate_world_create(facade, data)
    _raise_on_fail(validation)
    bundle = validation.normalized
    if isinstance(bundle, dict) and isinstance(bundle.get("world"), dict):
        return bundle["world"]
    return data


async def gate_world_update(
    container,
    world_uid: str,
    patch: dict[str, Any],
) -> None:
    existing = asdict(await container.world_service().get_by_id(world_uid))
    facade = container.json_validation_facade()
    validation = await validate_world_update(
        facade,
        existing=existing,
        patch=patch,
        world_uid=world_uid,
    )
    _raise_on_fail(validation)


async def gate_entity_create(
    container,
    world_uid: str,
    section: SectionKey,
    data: dict[str, Any],
) -> dict[str, Any]:
    world = asdict(await container.world_service().get_by_id(world_uid))
    seed_snapshot = None
    if section in SECTIONS_REQUIRING_SEED:
        seed_snapshot = await container.seed_service().export_all()
    row = {**data, "world_uid": world_uid}
    facade = container.json_validation_facade()
    validation = await validate_entity_row(
        facade,
        world=world,
        section=section,
        row=row,
        world_uid=world_uid,
        seed_snapshot=seed_snapshot,
    )
    _raise_on_fail(validation)
    bundle = validation.normalized
    if isinstance(bundle, dict):
        rows = bundle.get(section.value)
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            return rows[0]
    return row


async def gate_entity_update(
    container,
    world_uid: str,
    section: SectionKey,
    entity_uid: str,
    patch: dict[str, Any],
    *,
    load_existing,
    immutable: frozenset[str],
) -> None:
    existing_row = asdict(await load_existing(world_uid, entity_uid))
    merged = merge_shallow_patch(existing_row, patch, immutable=immutable)
    world = asdict(await container.world_service().get_by_id(world_uid))
    seed_snapshot = None
    if section in SECTIONS_REQUIRING_SEED:
        seed_snapshot = await container.seed_service().export_all()
    facade = container.json_validation_facade()
    validation = await validate_entity_row(
        facade,
        world=world,
        section=section,
        row=merged,
        world_uid=world_uid,
        seed_snapshot=seed_snapshot,
    )
    _raise_on_fail(validation)
