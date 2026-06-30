"""SCH-WORLD-REGISTRY-REFS — Pass 2 inbound refs in world registries (JV-2)."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._rowHelpers import check_ref

SCHEMA_ID = "SCH-WORLD-REGISTRY-REFS"

_N1S_LORE_FIELDS = ("stat_schema", "skill_schema", "resist_schema")


class RegistryRefsValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.WORLD})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors or ctx.index is None:
            return
        world = _world_blob(ctx)
        if world is None:
            return
        ctx.issues.extend(_collect_registry_ref_issues(world, ctx.index))


def _world_blob(ctx: ValidationContext) -> dict[str, Any] | None:
    bundle = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    if not isinstance(bundle, dict):
        return None
    world = bundle.get("world")
    return world if isinstance(world, dict) else None


def _collect_registry_ref_issues(
    world: dict[str, Any],
    index,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    terrain = world.get("terrain_registry")
    if isinstance(terrain, list):
        for i, row in enumerate(terrain):
            if not isinstance(row, dict):
                continue
            base = f"world.terrain_registry[{i}]"
            issues.extend(check_ref(
                index, RefKind.LORE, row.get("glossary_ref"), f"{base}.glossary_ref",
                SCHEMA_ID, field_name="glossary_ref",
            ))
            issues.extend(check_ref(
                index, RefKind.TERRAIN_CAT, row.get("terrain_category"), f"{base}.terrain_category",
                SCHEMA_ID, field_name="terrain_category",
            ))
            issues.extend(check_ref(
                index, RefKind.MATERIAL, row.get("default_material"), f"{base}.default_material",
                SCHEMA_ID, field_name="default_material",
            ))
            issues.extend(check_ref(
                index, RefKind.DANGER, row.get("danger_level"), f"{base}.danger_level",
                SCHEMA_ID, field_name="danger_level",
            ))

    materials = world.get("material_registry")
    if isinstance(materials, list):
        for i, row in enumerate(materials):
            if not isinstance(row, dict):
                continue
            issues.extend(check_ref(
                index, RefKind.LORE, row.get("glossary_ref"),
                f"world.material_registry[{i}].glossary_ref",
                SCHEMA_ID, field_name="glossary_ref",
            ))

    for field_name in _N1S_LORE_FIELDS:
        rows = world.get(field_name)
        if isinstance(rows, list):
            for i, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                issues.extend(check_ref(
                    index, RefKind.LORE, row.get("lore_ref"),
                    f"world.{field_name}[{i}].lore_ref",
                    SCHEMA_ID, field_name="lore_ref", severity="warn",
                ))

    return issues
