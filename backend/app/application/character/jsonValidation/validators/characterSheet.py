"""SCH-CHARACTER-SHEET — docs/tz_json_validation.md JV-6."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.application.character.jsonValidation.types import CharacterValidationContext
from app.application.worldData.generators.registries.wireEnums import SystemGender
from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import check_wire_enum

SCHEMA_ID = "SCH-CHARACTER-SHEET"


def validate_character_sheet(ctx: CharacterValidationContext) -> None:
    sheet = ctx.sheet
    if not isinstance(sheet, dict):
        return

    issues = ctx.issues
    issues.extend(check_wire_enum(
        SystemGender, sheet.get("system_gender"),
        "system_gender", SCHEMA_ID, field_name="system_gender",
    ))

    if ctx.index is not None:
        _validate_system_stats(sheet, ctx.stat_schema, ctx.index, issues)
        if ctx.seed_index is not None:
            _validate_seed_ref(
                sheet.get("system_age_type"), "system_age_type", "age_type", ctx.seed_index, issues,
            )
            _validate_seed_ref(
                sheet.get("system_social_status"), "system_social_status", "social_status",
                ctx.seed_index, issues,
            )

    if ctx.race_uids and sheet.get("system_race") is not None:
        race = sheet.get("system_race")
        if not isinstance(race, str) or race not in ctx.race_uids:
            issues.append(error(
                SCHEMA_ID, "system_race", "UNKNOWN_RACE",
                f"system_race {race!r} is not in world races",
            ))

    if ctx.location_uids:
        for field in ("system_home_location_uid", "system_home_settlement_uid", "system_location"):
            ref = sheet.get(field)
            if isinstance(ref, str) and ref and ref not in ctx.location_uids:
                issues.append(error(
                    SCHEMA_ID, field, "BROKEN_FK",
                    f"unknown location uid {ref!r}",
                ))


def _validate_seed_ref(
    value: Any,
    path: str,
    table: str,
    seed_index,
    issues: list,
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        issues.append(error(SCHEMA_ID, path, "INVALID_REF", f"{path} must be a non-empty string"))
        return
    if seed_index.keys(table) and not seed_index.has_seed(table, value):
        issues.append(error(
            SCHEMA_ID, path, "UNKNOWN_REF", f"unknown {table} key {value!r}",
        ))


def _validate_system_stats(
    sheet: dict[str, Any],
    stat_schema: dict[str, dict[str, Any]] | None,
    index,
    issues: list,
) -> None:
    stats = sheet.get("system_stats")
    if stats is None:
        return
    if not isinstance(stats, dict):
        issues.append(error(
            SCHEMA_ID, "system_stats", "INVALID_TYPE", "system_stats must be an object",
        ))
        return

    known = index.keys(RefKind.STAT)
    if not known:
        return

    for key, val in stats.items():
        if not isinstance(key, str):
            continue
        if key not in known:
            issues.append(error(
                SCHEMA_ID, f"system_stats.{key}", "UNKNOWN_STAT",
                f"stat key {key!r} is not in world stat_schema",
            ))
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            issues.append(error(
                SCHEMA_ID, f"system_stats.{key}", "INVALID_TYPE",
                f"stat {key!r} must be a number",
            ))
            continue
        if stat_schema and key in stat_schema:
            row = stat_schema[key]
            if isinstance(row, dict):
                min_v, max_v = row.get("min"), row.get("max")
                if isinstance(min_v, (int, float)) and val < min_v:
                    issues.append(error(
                        SCHEMA_ID, f"system_stats.{key}", "OUT_OF_RANGE",
                        f"stat {key!r} value {val} below min {min_v}",
                    ))
                if isinstance(max_v, (int, float)) and val > max_v:
                    issues.append(error(
                        SCHEMA_ID, f"system_stats.{key}", "OUT_OF_RANGE",
                        f"stat {key!r} value {val} above max {max_v}",
                    ))


def build_stat_schema_map(world: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map stat_schema keys to row dicts (supports map or array wire)."""
    raw = world.get("stat_schema")
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, dict)}
    if isinstance(raw, list):
        out: dict[str, dict[str, Any]] = {}
        for row in raw:
            if isinstance(row, dict) and isinstance(row.get("system_name"), str):
                out[row["system_name"]] = row
        return out
    return {}


def prepare_world_for_character_index(world: dict[str, Any]) -> dict[str, Any]:
    prepared = deepcopy(world)
    from app.application.worldData.jsonValidation.normalize.n1sSchemas import normalize_world_n1s
    normalize_world_n1s(prepared)
    return prepared
