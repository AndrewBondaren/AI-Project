"""CRUD patch validation (T3–T5) — docs/tz_json_validation.md."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.sectionImport import SECTIONS_REQUIRING_SEED
from app.application.worldData.jsonValidation.syntheticBundle import build_synthetic_bundle
from app.application.worldData.jsonValidation.types import (
    SectionKey,
    ValidationKind,
    ValidationRequest,
    ValidationResult,
)

_WORLD_IMMUTABLE = frozenset({"world_uid", "created_at"})


def merge_shallow_patch(
    base: dict[str, Any],
    patch: dict[str, Any],
    *,
    immutable: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Merge CRUD patch into existing row/world (top-level keys, same as services)."""
    merged = deepcopy(base)
    skip = immutable | _WORLD_IMMUTABLE
    for key, value in patch.items():
        if key in skip:
            continue
        merged[key] = deepcopy(value) if isinstance(value, (dict, list)) else value
    return merged


def build_world_crud_bundle(world_data: dict[str, Any]) -> dict[str, Any]:
    return {"world": deepcopy(world_data)}


def build_entity_crud_bundle(
    world: dict[str, Any],
    section: SectionKey,
    row: dict[str, Any],
) -> dict[str, Any]:
    return build_synthetic_bundle(world, section, [row])


async def validate_crud_patch(
    facade: JsonValidationFacade,
    *,
    bundle: dict[str, Any],
    section: SectionKey | None,
    world_uid: str | None = None,
    seed_snapshot: dict[str, list[dict]] | None = None,
) -> ValidationResult:
    return await facade.validate(ValidationRequest(
        kind=ValidationKind.CRUD_PATCH,
        payload=bundle,
        section=section,
        world_uid=world_uid,
        seed_snapshot=seed_snapshot,
    ))


async def validate_world_create(
    facade: JsonValidationFacade,
    world_data: dict[str, Any],
) -> ValidationResult:
    uid = world_data.get("world_uid") if isinstance(world_data.get("world_uid"), str) else None
    return await validate_crud_patch(
        facade,
        bundle=build_world_crud_bundle(world_data),
        section=SectionKey.WORLD,
        world_uid=uid,
    )


async def validate_world_update(
    facade: JsonValidationFacade,
    *,
    existing: dict[str, Any],
    patch: dict[str, Any],
    world_uid: str,
) -> ValidationResult:
    merged = merge_shallow_patch(existing, patch)
    return await validate_crud_patch(
        facade,
        bundle=build_world_crud_bundle(merged),
        section=SectionKey.WORLD,
        world_uid=world_uid,
    )


async def validate_entity_row(
    facade: JsonValidationFacade,
    *,
    world: dict[str, Any],
    section: SectionKey,
    row: dict[str, Any],
    world_uid: str,
    seed_snapshot: dict[str, list[dict]] | None = None,
) -> ValidationResult:
    return await validate_crud_patch(
        facade,
        bundle=build_entity_crud_bundle(world, section, row),
        section=section,
        world_uid=world_uid,
        seed_snapshot=seed_snapshot,
    )
