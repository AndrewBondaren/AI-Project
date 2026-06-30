"""Location cross-row helpers — docs/tz_json_validation.md JV-2."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.types import ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error

SCHEMA_ID = "SCH-NAMED-LOCATION-ROW"


def parent_types_by_loc_type(world: dict[str, Any] | None) -> dict[str, frozenset[str]]:
    if not isinstance(world, dict):
        return {}
    reg = world.get("location_type_registry")
    out: dict[str, frozenset[str]] = {}
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
        parents = row.get("parent_types")
        if isinstance(parents, list):
            out[type_key] = frozenset(p for p in parents if isinstance(p, str))
    return out


def collect_parent_type_issues(
    locations: list[Any],
    parent_types_map: dict[str, frozenset[str]],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    by_uid = {
        row["location_uid"]: row
        for row in locations
        if isinstance(row, dict) and isinstance(row.get("location_uid"), str)
    }
    for i, row in enumerate(locations):
        if not isinstance(row, dict):
            continue
        child_type = row.get("system_location_type")
        parent_uid = row.get("parent_location_uid")
        if not isinstance(child_type, str) or not isinstance(parent_uid, str):
            continue
        allowed = parent_types_map.get(child_type)
        if not allowed:
            continue
        parent = by_uid.get(parent_uid)
        if not isinstance(parent, dict):
            continue
        parent_type = parent.get("system_location_type")
        if isinstance(parent_type, str) and parent_type not in allowed:
            issues.append(error(
                SCHEMA_ID, f"locations[{i}].parent_location_uid", "INVALID_PARENT_TYPE",
                f"parent type {parent_type!r} not in parent_types for {child_type!r}",
            ))
    return issues


def collect_room_building_ancestor_issues(locations: list[Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    by_uid = {
        row["location_uid"]: row
        for row in locations
        if isinstance(row, dict) and isinstance(row.get("location_uid"), str)
    }
    for i, row in enumerate(locations):
        if not isinstance(row, dict) or row.get("system_location_type") != "room":
            continue
        uid = row.get("location_uid")
        if not isinstance(uid, str):
            continue
        if not _has_building_ancestor(uid, by_uid):
            issues.append(error(
                SCHEMA_ID, f"locations[{i}]", "MISSING_BUILDING_ANCESTOR",
                f"room {uid!r} requires a building ancestor",
            ))
    return issues


def _has_building_ancestor(uid: str, by_uid: dict[str, dict[str, Any]]) -> bool:
    visited: set[str] = set()
    current: str | None = uid
    while current:
        if current in visited:
            return False
        visited.add(current)
        row = by_uid.get(current)
        if not isinstance(row, dict):
            return False
        if row.get("system_location_type") == "building":
            return True
        parent = row.get("parent_location_uid")
        if not isinstance(parent, str):
            return False
        current = parent
    return False
