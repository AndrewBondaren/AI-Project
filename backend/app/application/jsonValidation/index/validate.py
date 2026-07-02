"""REF-W semantic checks on normalized ``worlds`` wire — import only."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.application.jsonValidation.index.build import build_world_registry_index
from app.application.jsonValidation.index.refKinds import RefKind
from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.jsonValidation.types import FieldPathError
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry


@dataclass(frozen=True)
class RefCheck:
    ref_kind: RefKind
    schema_id: str
    path: tuple[str, ...]
    value_getter: Callable[[dict[str, Any]], str | None]
    registry_present_key: str | None = None


def _ref_error(
    *,
    schema_id: str,
    path: tuple[str, ...],
    ref_kind: RefKind,
    value: str,
) -> FieldPathError:
    return FieldPathError(
        path=path,
        message=f"unknown {ref_kind.value} target: {value!r}",
        schema_id=schema_id,
        code="REF_W_UNKNOWN",
    )


def _check_ref(
    index: WorldRegistryIndex,
    *,
    schema_id: str,
    path: tuple[str, ...],
    ref_kind: RefKind,
    value: str | None,
    registry_available: bool,
) -> FieldPathError | None:
    if value is None or value == "":
        return None
    if not registry_available:
        return None
    allowed = index.keys_for(ref_kind)
    if allowed is None:
        return None
    if value in allowed:
        return None
    return _ref_error(schema_id=schema_id, path=path, ref_kind=ref_kind, value=value)


def _climate_scalar_checks(normalized: dict[str, Any], partial: bool) -> list[RefCheck]:
    checks: list[RefCheck] = []
    if not partial or "precipitation_liquid" in normalized:
        checks.append(
            RefCheck(
                ref_kind=RefKind.LIQUID,
                schema_id=WorldClimateScalars.SCHEMA_ID,
                path=("precipitation_liquid",),
                value_getter=lambda data: data.get("precipitation_liquid"),
                registry_present_key="material_registry",
            ),
        )
    if not partial or "default_climate_zone" in normalized:
        checks.append(
            RefCheck(
                ref_kind=RefKind.CLIMATE,
                schema_id=WorldClimateScalars.SCHEMA_ID,
                path=("default_climate_zone",),
                value_getter=lambda data: data.get("default_climate_zone"),
                registry_present_key="climate_zone_registry",
            ),
        )
    return checks


def _hydrology_checks(normalized: dict[str, Any], partial: bool) -> list[RefCheck]:
    if partial and "hydrology" not in normalized:
        return []

    hydrology = normalized.get("hydrology")
    if not isinstance(hydrology, dict):
        return []

    shore = hydrology.get("default_shore")
    if not isinstance(shore, dict):
        return []

    return [
        RefCheck(
            ref_kind=RefKind.TERRAIN,
            schema_id=WorldHydrology.SCHEMA_ID,
            path=("hydrology", "default_shore", "system_terrain"),
            value_getter=lambda _: shore.get("system_terrain"),
            registry_present_key="terrain_registry",
        ),
        RefCheck(
            ref_kind=RefKind.MATERIAL,
            schema_id=WorldHydrology.SCHEMA_ID,
            path=("hydrology", "default_shore", "system_material"),
            value_getter=lambda _: shore.get("system_material"),
            registry_present_key="material_registry",
        ),
    ]


def _material_tier_checks(normalized: dict[str, Any], partial: bool) -> list[RefCheck]:
    if partial and "material_registry" not in normalized:
        return []

    rows = normalized.get("material_registry")
    if not isinstance(rows, list):
        return []

    checks: list[RefCheck] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        tier = row.get("economic_tier")
        if tier is None:
            continue
        checks.append(
            RefCheck(
                ref_kind=RefKind.ECON_TIER,
                schema_id=WorldMaterialRegistry.SCHEMA_ID,
                path=("material_registry", index, "economic_tier"),
                value_getter=lambda _data, tier=tier: tier,
                registry_present_key="economic_tier_registry",
            ),
        )
    return checks


def validate_ref_w(
    normalized: dict[str, Any],
    *,
    partial: bool,
) -> list[FieldPathError]:
    """Run REF-W rules after ``merge_facade_slices`` (import / CRUD write)."""
    index = build_world_registry_index(normalized, partial=partial)
    checks = [
        *_climate_scalar_checks(normalized, partial),
        *_hydrology_checks(normalized, partial),
        *_material_tier_checks(normalized, partial),
    ]

    errors: list[FieldPathError] = []
    for check in checks:
        value = check.value_getter(normalized)
        registry_available = (
            check.registry_present_key is None
            or check.registry_present_key in normalized
            or not partial
        )
        issue = _check_ref(
            index,
            schema_id=check.schema_id,
            path=check.path,
            ref_kind=check.ref_kind,
            value=value,
            registry_available=registry_available,
        )
        if issue is not None:
            errors.append(issue)
    return errors
