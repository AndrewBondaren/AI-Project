"""N1-W registry normalize — docs/tz_json_validation.md JV-1 N1-W-07, N1-W-08."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.types import ValidationIssue


def _issue(path: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(
        schema_id="N1-W-normalize",
        path=path,
        code=code,
        message=message,
    )


def normalize_location_type_registry(world: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    reg = world.get("location_type_registry")
    if reg is None:
        return issues
    if isinstance(reg, list):
        return issues
    if not isinstance(reg, dict):
        issues.append(_issue(
            "world.location_type_registry", "INVALID_TYPE",
            "location_type_registry must be an object or array",
        ))
        return issues
    rows: list[dict[str, Any]] = []
    for system_type, entry in reg.items():
        if not isinstance(system_type, str):
            continue
        row = dict(entry) if isinstance(entry, dict) else {}
        row["system_type"] = system_type
        if "display_type" not in row and isinstance(row.get("display_name"), str):
            row["display_type"] = row.pop("display_name")
        rows.append(row)
    world["location_type_registry"] = rows
    return issues


def normalize_city_size_registry(world: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    reg = world.get("city_size_registry")
    if not isinstance(reg, list):
        return issues
    for i, row in enumerate(reg):
        if not isinstance(row, dict):
            continue
        if "map_cells_count" not in row and "radius" in row:
            radius = row.get("radius")
            if isinstance(radius, int) and not isinstance(radius, bool):
                row["map_cells_count"] = radius
    return issues


def normalize_world_registries(world: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(normalize_location_type_registry(world))
    issues.extend(normalize_city_size_registry(world))
    return issues
