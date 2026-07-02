"""SCH-NAMED-LOCATION-ROW — docs/tz_json_validation.md JV-2."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.climatePole import CLIMATE_POLE_TYPE
from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import (
    check_fk,
    check_ref,
    collect_duplicate_uids,
    detect_parent_cycles,
)

SCHEMA_ID = "SCH-NAMED-LOCATION-ROW"


class NamedLocationRowValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.LOCATIONS})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors or ctx.index is None:
            return
        bundle = _bundle(ctx)
        if bundle is None:
            return
        locations = bundle.get("locations")
        if not isinstance(locations, list):
            return
        ctx.issues.extend(collect_location_issues(locations, bundle, ctx.index))


def _bundle(ctx: ValidationContext) -> dict[str, Any] | None:
    blob = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    return blob if isinstance(blob, dict) else None


def collect_location_issues(
    locations: list[Any],
    bundle: dict[str, Any],
    index,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(collect_duplicate_uids(locations, "location_uid", "locations", SCHEMA_ID))

    location_uids = {
        row["location_uid"]
        for row in locations
        if isinstance(row, dict) and isinstance(row.get("location_uid"), str)
    }
    state_uids = _state_uids(bundle)

    dict_rows = [row for row in locations if isinstance(row, dict)]
    issues.extend(detect_parent_cycles(
        dict_rows, "location_uid", "parent_location_uid", "locations", SCHEMA_ID,
    ))

    pole_count = 0
    subtype_index = index.keys(RefKind.LOC_SUBTYPE)

    for i, row in enumerate(locations):
        if not isinstance(row, dict):
            issues.append(error(
                SCHEMA_ID, f"locations[{i}]", "INVALID_ROW", "location row must be an object",
            ))
            continue
        base = f"locations[{i}]"
        uid = row.get("location_uid")
        if not isinstance(uid, str) or not uid:
            continue

        for field in ("display_name", "system_location_type", "created_at"):
            val = row.get(field)
            if not isinstance(val, str) or not val:
                issues.append(error(
                    SCHEMA_ID, f"{base}.{field}", "MISSING_FIELD", f"{field} is required",
                ))

        loc_type = row.get("system_location_type")
        issues.extend(check_ref(
            index, RefKind.LOC_TYPE, loc_type, f"{base}.system_location_type",
            SCHEMA_ID, field_name="system_location_type",
        ))

        subtype = row.get("system_location_subtype")
        if subtype is not None and subtype_index:
            issues.extend(check_ref(
                index, RefKind.LOC_SUBTYPE, subtype, f"{base}.system_location_subtype",
                SCHEMA_ID, field_name="system_location_subtype",
            ))

        issues.extend(check_fk(
            row.get("parent_location_uid"), location_uids, f"{base}.parent_location_uid",
            SCHEMA_ID, field_name="parent_location_uid",
        ))
        issues.extend(check_fk(
            row.get("state_uid"), state_uids, f"{base}.state_uid",
            SCHEMA_ID, field_name="state_uid",
        ))
        issues.extend(check_ref(
            index, RefKind.CITY_SIZE, row.get("system_city_size"), f"{base}.system_city_size",
            SCHEMA_ID, field_name="system_city_size",
        ))
        issues.extend(check_ref(
            index, RefKind.CLIMATE, row.get("system_climate_zone"), f"{base}.system_climate_zone",
            SCHEMA_ID, field_name="system_climate_zone",
        ))
        issues.extend(check_ref(
            index, RefKind.MATERIAL, row.get("parent_wall_material"), f"{base}.parent_wall_material",
            SCHEMA_ID, field_name="parent_wall_material",
        ))
        issues.extend(check_ref(
            index, RefKind.MATERIAL, row.get("parent_floor_material"), f"{base}.parent_floor_material",
            SCHEMA_ID, field_name="parent_floor_material",
        ))
        issues.extend(check_ref(
            index, RefKind.LORE, row.get("glossary_ref"), f"{base}.glossary_ref",
            SCHEMA_ID, field_name="glossary_ref", severity="warn",
        ))

        tag_refs = row.get("tag_refs")
        if isinstance(tag_refs, list):
            for j, tag in enumerate(tag_refs):
                issues.extend(check_ref(
                    index, RefKind.TAG, tag, f"{base}.tag_refs[{j}]",
                    SCHEMA_ID, field_name="tag_ref", severity="warn",
                ))

        if loc_type == CLIMATE_POLE_TYPE:
            pole_count += 1

    if pole_count > 1:
        issues.append(error(
            SCHEMA_ID, "locations", "CLIMATE_POLE_LIMIT",
            "At most one climate_pole location per world import",
        ))

    return issues


def _state_uids(bundle: dict[str, Any]) -> set[str]:
    states = bundle.get("states")
    if not isinstance(states, list):
        return set()
    return {
        row["state_uid"]
        for row in states
        if isinstance(row, dict) and isinstance(row.get("state_uid"), str)
    }
