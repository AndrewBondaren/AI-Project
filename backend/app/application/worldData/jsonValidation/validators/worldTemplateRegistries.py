"""World template registries — building/district/barrier on world blob (JV-4/5)."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import check_ref
from app.application.worldData.jsonValidation.validators.templates.barrierTemplate import (
    collect_barrier_template_issues,
)
from app.application.worldData.jsonValidation.validators.templates.buildingTemplate import (
    collect_building_template_issues,
)
from app.application.worldData.jsonValidation.validators.templates.districtTemplate import (
    collect_district_template_issues,
)

SCHEMA_ID = "SCH-WORLD-TEMPLATE-REGISTRIES"


class WorldTemplateRegistriesValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.WORLD})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors or ctx.index is None:
            return
        world = _world_blob(ctx)
        if world is None:
            return
        ctx.issues.extend(collect_world_template_registry_issues(world, ctx.index))


def _world_blob(ctx: ValidationContext) -> dict[str, Any] | None:
    bundle = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    if not isinstance(bundle, dict):
        return None
    world = bundle.get("world")
    return world if isinstance(world, dict) else None


def collect_world_template_registry_issues(world: dict[str, Any], index) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_validate_building_registry(world, index))
    issues.extend(_validate_district_registry(world, index))
    issues.extend(_validate_barrier_registry(world, index))
    return issues


def _iter_registry_entries(registry: Any) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(registry, list):
        out: list[tuple[str, dict[str, Any]]] = []
        for i, entry in enumerate(registry):
            if not isinstance(entry, dict):
                continue
            key = entry.get("system_name") or entry.get("system_template_uid") or str(i)
            out.append((str(key), entry))
        return out
    if isinstance(registry, dict):
        return [(str(k), v) for k, v in registry.items() if isinstance(v, dict)]
    return []


def _validate_building_registry(world: dict[str, Any], index) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    registry = world.get("building_template_registry")
    if registry is None:
        return issues
    for key, entry in _iter_registry_entries(registry):
        base = f"world.building_template_registry.{key}"
        if "levels" in entry:
            issues.extend(collect_building_template_issues(entry, index=index, path_prefix=base))
        else:
            uid = entry.get("system_template_uid")
            if not isinstance(uid, str) or not uid:
                issues.append(error(
                    SCHEMA_ID, f"{base}.system_template_uid", "MISSING_FIELD",
                    "registry entry requires system_template_uid or full template body",
                ))
            elif not index.has_ref(RefKind.BUILDING_TPL, uid) and entry.get("system_name") is None:
                issues.extend(check_ref(
                    index, RefKind.BUILDING_TPL, uid, f"{base}.system_template_uid",
                    SCHEMA_ID, field_name="system_template_uid",
                ))
    return issues


def _validate_district_registry(world: dict[str, Any], index) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    registry = world.get("district_template_registry")
    if registry is None:
        return issues
    for key, entry in _iter_registry_entries(registry):
        issues.extend(collect_district_template_issues(
            entry, index=index, path_prefix=f"world.district_template_registry.{key}",
        ))
    return issues


def _validate_barrier_registry(world: dict[str, Any], index) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    registry = world.get("barrier_template_registry")
    if registry is None:
        return issues
    for key, entry in _iter_registry_entries(registry):
        issues.extend(collect_barrier_template_issues(
            entry, index=index, path_prefix=f"world.barrier_template_registry.{key}",
        ))
    return issues
