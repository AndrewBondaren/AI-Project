"""SCH-WORLD-REGISTRY-REFS — Pass 2 inbound refs in world registries (JV-2)."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.generators.registries.wireEnums import (
    BorderCategory,
    CellStateCategory,
    MaterialCategory,
)
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._rowHelpers import check_ref, check_wire_enum

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
            base = f"world.material_registry[{i}]"
            issues.extend(check_ref(
                index, RefKind.LORE, row.get("glossary_ref"),
                f"{base}.glossary_ref",
                SCHEMA_ID, field_name="glossary_ref",
            ))
            issues.extend(check_wire_enum(
                MaterialCategory, row.get("material_category"),
                f"{base}.material_category", SCHEMA_ID, field_name="material_category",
            ))

    cell_states = world.get("cell_state_registry")
    if isinstance(cell_states, list):
        for i, row in enumerate(cell_states):
            if not isinstance(row, dict):
                continue
            issues.extend(check_wire_enum(
                CellStateCategory, row.get("state_category"),
                f"world.cell_state_registry[{i}].state_category",
                SCHEMA_ID, field_name="state_category",
            ))
    elif isinstance(cell_states, dict):
        for key, row in cell_states.items():
            if not isinstance(row, dict):
                continue
            issues.extend(check_wire_enum(
                CellStateCategory, row.get("state_category"),
                f"world.cell_state_registry.{key}.state_category",
                SCHEMA_ID, field_name="state_category",
            ))

    issues.extend(_validate_location_type_registry(world))

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


def _validate_location_type_registry(world: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    reg = world.get("location_type_registry")
    entries: list[tuple[str, dict[str, Any]]] = []
    if isinstance(reg, list):
        for row in reg:
            if isinstance(row, dict) and isinstance(row.get("system_type"), str):
                entries.append((row["system_type"], row))
    elif isinstance(reg, dict):
        for key, row in reg.items():
            if isinstance(key, str) and isinstance(row, dict):
                entries.append((key, row))
    for type_key, row in entries:
        subtypes = row.get("subtypes")
        if not isinstance(subtypes, list):
            continue
        for j, sub in enumerate(subtypes):
            if not isinstance(sub, dict):
                continue
            border = sub.get("border_category")
            if border is not None:
                issues.extend(check_wire_enum(
                    BorderCategory, border,
                    f"world.location_type_registry.{type_key}.subtypes[{j}].border_category",
                    SCHEMA_ID, field_name="border_category",
                ))
    return issues
