"""Section import validation (T2) — docs/tz_json_validation.md."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.facade import JsonValidationFacade
from app.application.worldData.jsonValidation.syntheticBundle import build_synthetic_bundle
from app.application.worldData.jsonValidation.types import (
    SectionKey,
    ValidationKind,
    ValidationRequest,
    ValidationResult,
)

# Seed tables required for race contract refs during section import.
SECTIONS_REQUIRING_SEED: frozenset[SectionKey] = frozenset({SectionKey.RACES})


async def validate_section_import(
    facade: JsonValidationFacade,
    *,
    world: dict[str, Any],
    section: SectionKey,
    payload: list[Any] | dict[str, Any],
    world_uid: str,
    seed_snapshot: dict[str, list[dict]] | None = None,
) -> ValidationResult:
    synthetic = build_synthetic_bundle(world, section, payload)
    return await facade.validate(ValidationRequest(
        kind=ValidationKind.SECTION,
        payload=synthetic,
        section=section,
        world_uid=world_uid,
        seed_snapshot=seed_snapshot,
    ))
