"""SCH-BUILDING-TEMPLATE — docs/tz_building_generator.md §10, JV-4."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.application.worldData.generators.registries.wireEnums import (
    BuildingContext,
    GapPolicy,
    StaircaseType,
)
from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import check_ref, check_wire_enum

SCHEMA_ID = "SCH-BUILDING-TEMPLATE"

_SIZE_TYPES = frozenset({"small", "medium", "big", "huge", "colossal"})


def collect_building_template_issues(
    data: dict[str, Any],
    *,
    index=None,
    path_prefix: str = "",
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    base = path_prefix or "$"

    if not isinstance(data, dict):
        return [error(SCHEMA_ID, base, "INVALID_TYPE", "building template must be an object")]

    for field in ("system_name", "structure_type", "display_name", "version"):
        val = data.get(field)
        path = f"{base}.{field}" if base != "$" else field
        if not isinstance(val, str) or not val:
            issues.append(error(SCHEMA_ID, path, "MISSING_FIELD", f"{field} is required"))

    if data.get("gap_policy") is not None:
        issues.extend(check_wire_enum(
            GapPolicy, data["gap_policy"], f"{base}.gap_policy", SCHEMA_ID, field_name="gap_policy",
        ))
    if data.get("building_context") is not None:
        issues.extend(check_wire_enum(
            BuildingContext, data["building_context"], f"{base}.building_context", SCHEMA_ID,
            field_name="building_context",
        ))
    if data.get("economic_tier") is not None and index is not None:
        issues.extend(check_ref(
            index, RefKind.ECON_TIER, data.get("economic_tier"),
            f"{base}.economic_tier", SCHEMA_ID, field_name="economic_tier",
        ))

    levels = data.get("levels")
    if not isinstance(levels, list) or not levels:
        issues.append(error(
            SCHEMA_ID, f"{base}.levels", "MISSING_FIELD", "levels must be a non-empty array",
        ))
        return issues

    all_room_ids: list[str] = []
    for level in levels:
        if not isinstance(level, dict):
            continue
        for room in level.get("rooms") or []:
            if isinstance(room, dict) and isinstance(room.get("room_id"), str):
                all_room_ids.append(room["room_id"])
    for rid, count in Counter(all_room_ids).items():
        if count > 1:
            issues.append(error(
                SCHEMA_ID, base, "DUP_ROOM_ID", f"duplicate room_id {rid!r}",
            ))
    room_ids = set(all_room_ids)

    entry_count = 0
    back_entry_count = 0
    z_by_room: dict[str, int] = {}

    for li, level in enumerate(levels):
        lbase = f"{base}.levels[{li}]"
        if not isinstance(level, dict):
            issues.append(error(SCHEMA_ID, lbase, "INVALID_ENTRY", "level must be an object"))
            continue

        z_off = level.get("z_offset")
        if not isinstance(z_off, int) or isinstance(z_off, bool):
            issues.append(error(SCHEMA_ID, f"{lbase}.z_offset", "MISSING_FIELD", "z_offset is required"))
        elif not isinstance(level.get("display_name"), str) or not level.get("display_name"):
            issues.append(error(SCHEMA_ID, f"{lbase}.display_name", "MISSING_FIELD", "display_name is required"))

        rooms = level.get("rooms")
        if not isinstance(rooms, list) or not rooms:
            issues.append(error(SCHEMA_ID, f"{lbase}.rooms", "MISSING_FIELD", "rooms must be a non-empty array"))
            continue

        for ri, room in enumerate(rooms):
            rbase = f"{lbase}.rooms[{ri}]"
            if not isinstance(room, dict):
                issues.append(error(SCHEMA_ID, rbase, "INVALID_ENTRY", "room must be an object"))
                continue
            room_issues, has_entry, has_back = _validate_room(room, rbase, index, room_ids)
            issues.extend(room_issues)
            entry_count += has_entry
            back_entry_count += has_back
            rid = room.get("room_id")
            if isinstance(rid, str) and isinstance(z_off, int) and not isinstance(z_off, bool):
                z_by_room[rid] = z_off

    if entry_count > 1:
        issues.append(error(SCHEMA_ID, base, "DUPLICATE_ENTRY", "at most one room may declare entry_point"))
    if back_entry_count > 1:
        issues.append(error(SCHEMA_ID, base, "DUPLICATE_ENTRY", "at most one room may declare back_entry_point"))

    issues.extend(_validate_connections(data, base, room_ids))
    issues.extend(_validate_staircases(data, base, room_ids, z_by_room))
    return issues


def _validate_room(
    room: dict[str, Any],
    path: str,
    index,
    room_ids: set[str],
) -> tuple[list[ValidationIssue], int, int]:
    issues: list[ValidationIssue] = []
    for field in ("room_id", "room_type", "display_name", "shape_type"):
        if not isinstance(room.get(field), str) or not room.get(field):
            issues.append(error(SCHEMA_ID, f"{path}.{field}", "MISSING_FIELD", f"{field} is required"))

    for field in ("is_public", "is_forbidden", "required"):
        if field not in room:
            issues.append(error(SCHEMA_ID, f"{path}.{field}", "MISSING_FIELD", f"{field} is required"))

    if room.get("room_type") == "staircase":
        issues.append(error(
            SCHEMA_ID, f"{path}.room_type", "INVALID_ROOM_TYPE",
            "staircase rooms must use staircases[], not levels[].rooms",
        ))

    rid = room.get("room_id")

    has_entry = 1 if room.get("entry_point") is not None else 0
    has_back = 1 if room.get("back_entry_point") is not None else 0

    if index is not None:
        issues.extend(check_ref(
            index, RefKind.ROOM_TYPE, room.get("room_type"),
            f"{path}.room_type", SCHEMA_ID, field_name="room_type",
        ))
        if room.get("economic_tier") is not None:
            issues.extend(check_ref(
                index, RefKind.ECON_TIER, room.get("economic_tier"),
                f"{path}.economic_tier", SCHEMA_ID, field_name="economic_tier",
            ))

    issues.extend(_validate_room_size(room.get("size"), f"{path}.size"))

    if room.get("required") is False and room.get("count_range") is None:
        issues.append(error(
            SCHEMA_ID, f"{path}.count_range", "MISSING_FIELD",
            f"room {rid!r}: required=false requires count_range",
        ))
    cr = room.get("count_range")
    if isinstance(cr, list) and len(cr) == 2 and cr[0] < 1:
        issues.append(error(
            SCHEMA_ID, f"{path}.count_range", "OUT_OF_RANGE",
            f"room {rid!r}: count_range minimum must be >= 1",
        ))

    attach = room.get("attach_to")
    if isinstance(attach, str) and attach and attach not in room_ids:
        issues.append(error(
            SCHEMA_ID, f"{path}.attach_to", "BROKEN_REF",
            f"attach_to references unknown room_id {attach!r}",
        ))

    if room.get("outside") is True and room.get("has_walls") is False:
        issues.append(error(SCHEMA_ID, path, "INVALID_FIELD", "outside requires has_walls: true"))
    if room.get("outside") is True and room.get("in_a_room") is True:
        issues.append(error(SCHEMA_ID, path, "INVALID_FIELD", "outside and in_a_room are incompatible"))

    return issues, has_entry, has_back


def _validate_room_size(size: Any, path: str) -> list[ValidationIssue]:
    if not isinstance(size, dict):
        return [error(SCHEMA_ID, path, "MISSING_FIELD", "size is required")]
    issues: list[ValidationIssue] = []
    size_type = size.get("size_type")
    has_ranges = "width_range" in size or "depth_range" in size
    if size_type is not None:
        if size_type not in _SIZE_TYPES:
            issues.append(error(SCHEMA_ID, f"{path}.size_type", "UNKNOWN_ENUM", f"unknown size_type {size_type!r}"))
        if has_ranges:
            issues.append(error(
                SCHEMA_ID, path, "INVALID_SIZE",
                "size_type cannot be combined with width_range/depth_range",
            ))
    elif size.get("width_range") is None:
        issues.append(error(
            SCHEMA_ID, path, "INVALID_SIZE",
            "size must define size_type or width_range/depth_range",
        ))
    for range_name in ("width_range", "depth_range", "z_range"):
        rng = size.get(range_name)
        if rng is None:
            continue
        if not isinstance(rng, list) or len(rng) != 2:
            issues.append(error(SCHEMA_ID, f"{path}.{range_name}", "INVALID_RANGE", f"{range_name} must be [min, max]"))
        elif rng[0] > rng[1]:
            issues.append(error(SCHEMA_ID, f"{path}.{range_name}", "INVALID_RANGE", f"{range_name}[0] must be <= [1]"))
    return issues


def _validate_connections(data: dict[str, Any], base: str, room_ids: set[str]) -> list[ValidationIssue]:
    connections = data.get("connections")
    if connections is None:
        return []
    if not isinstance(connections, list):
        return [error(SCHEMA_ID, f"{base}.connections", "INVALID_TYPE", "connections must be an array")]
    issues: list[ValidationIssue] = []
    for i, conn in enumerate(connections):
        if not isinstance(conn, dict):
            continue
        cbase = f"{base}.connections[{i}]"
        if conn.get("passage_type") == "staircase":
            issues.append(error(
                SCHEMA_ID, f"{cbase}.passage_type", "INVALID_PASSAGE",
                'use staircases[] instead of passage_type "staircase"',
            ))
        for end in ("from_room", "to_room"):
            ref = conn.get(end)
            if isinstance(ref, str) and ref not in room_ids:
                issues.append(error(
                    SCHEMA_ID, f"{cbase}.{end}", "BROKEN_REF", f"unknown room_id {ref!r}",
                ))
    return issues


def _validate_staircases(
    data: dict[str, Any],
    base: str,
    room_ids: set[str],
    z_by_room: dict[str, int],
) -> list[ValidationIssue]:
    staircases = data.get("staircases")
    if staircases is None:
        return []
    if not isinstance(staircases, list):
        return [error(SCHEMA_ID, f"{base}.staircases", "INVALID_TYPE", "staircases must be an array")]
    issues: list[ValidationIssue] = []
    for i, stair in enumerate(staircases):
        if not isinstance(stair, dict):
            continue
        sbase = f"{base}.staircases[{i}]"
        if stair.get("staircase_type") is not None:
            issues.extend(check_wire_enum(
                StaircaseType, stair["staircase_type"], f"{sbase}.staircase_type", SCHEMA_ID,
                field_name="staircase_type",
            ))
        stops = stair.get("stops")
        if not isinstance(stops, list) or len(stops) < 2:
            issues.append(error(
                SCHEMA_ID, f"{sbase}.stops", "INVALID_STOPS", "staircases[].stops requires at least 2 room ids",
            ))
            continue
        prev_z: int | None = None
        for j, stop in enumerate(stops):
            if not isinstance(stop, str) or stop not in room_ids:
                issues.append(error(
                    SCHEMA_ID, f"{sbase}.stops[{j}]", "BROKEN_REF", f"unknown stop room_id {stop!r}",
                ))
                continue
            z = z_by_room.get(stop)
            if z is not None:
                if prev_z is not None and z < prev_z:
                    issues.append(error(
                        SCHEMA_ID, f"{sbase}.stops", "INVALID_ORDER",
                        "stops must be ordered bottom-to-top by level z_offset",
                    ))
                    break
                prev_z = z
    return issues
