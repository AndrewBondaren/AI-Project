"""SCH-RACE-CONTRACT — docs/tz_json_validation.md JV-8, tz_races.md."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import check_ref
from app.application.worldData.jsonValidation.validators.raceRow import (
    _GENDER_COLUMNS,
    _races,
)

SCHEMA_ID = "SCH-RACE-CONTRACT"

_APPEARANCE_TYPE_KEYS: tuple[tuple[str, str], ...] = (
    ("hair_types", "hair_type"),
    ("skin_types", "skin_type"),
    ("beard_types", "beard_type"),
    ("brows_types", "brows_type"),
)


class RaceContractValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.RACES})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors:
            return
        races = _races(ctx)
        if races is None:
            return
        ctx.issues.extend(collect_race_contract_issues(races, ctx.index, ctx.seed_index))


def collect_race_contract_issues(
    races: list[Any],
    index,
    seed_index,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for i, row in enumerate(races):
        if not isinstance(row, dict):
            continue
        base = f"races[{i}]"
        traits = row.get("race_traits")
        if isinstance(traits, dict):
            issues.extend(_validate_race_traits(traits, f"{base}.race_traits", index))
        for gender in _GENDER_COLUMNS:
            blob = row.get(gender)
            if isinstance(blob, dict):
                issues.extend(_validate_gender_blob(
                    blob, f"{base}.{gender}", index, seed_index,
                ))
    return issues


def _validate_race_traits(traits: dict[str, Any], path: str, index) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    terrain = traits.get("terrain_access")
    if terrain is not None:
        if not isinstance(terrain, list):
            issues.append(error(SCHEMA_ID, f"{path}.terrain_access", "INVALID_TYPE", "must be an array"))
        elif index is not None:
            for j, cat in enumerate(terrain):
                if isinstance(cat, str):
                    issues.extend(check_ref(
                        index, RefKind.TERRAIN_CAT, cat,
                        f"{path}.terrain_access[{j}]", SCHEMA_ID, field_name="terrain_category",
                    ))
    tags = traits.get("tag_refs")
    if tags is not None:
        if not isinstance(tags, list):
            issues.append(error(SCHEMA_ID, f"{path}.tag_refs", "INVALID_TYPE", "must be an array"))
        elif index is not None:
            for j, tag in enumerate(tags):
                if isinstance(tag, str):
                    issues.extend(check_ref(
                        index, RefKind.TAG, tag,
                        f"{path}.tag_refs[{j}]", SCHEMA_ID, field_name="tag_ref", severity="warn",
                    ))
    ticks = traits.get("sleep_requirement_ticks")
    if ticks is not None and (not isinstance(ticks, int) or isinstance(ticks, bool) or ticks < 0):
        issues.append(error(
            SCHEMA_ID, f"{path}.sleep_requirement_ticks", "OUT_OF_RANGE",
            "sleep_requirement_ticks must be an integer >= 0",
        ))
    return issues


def _validate_gender_blob(
    blob: dict[str, Any],
    path: str,
    index,
    seed_index,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_validate_lifespan(blob.get("lifespan"), f"{path}.lifespan", seed_index))
    issues.extend(_validate_measurement_range(blob.get("height_range"), f"{path}.height_range"))
    issues.extend(_validate_measurement_range(blob.get("weight_range"), f"{path}.weight_range"))

    applicable = blob.get("applicable_fields")
    if applicable is not None and not isinstance(applicable, dict):
        issues.append(error(
            SCHEMA_ID, f"{path}.applicable_fields", "INVALID_TYPE", "must be an object",
        ))
    elif isinstance(applicable, dict):
        for key, val in applicable.items():
            if not isinstance(val, bool):
                issues.append(error(
                    SCHEMA_ID, f"{path}.applicable_fields.{key}", "INVALID_TYPE",
                    "applicable_fields values must be booleans",
                ))

    if index is not None:
        for field, ref_kind in (
            ("muscle_stat", RefKind.STAT),
            ("constitution_stat", RefKind.STAT),
        ):
            issues.extend(check_ref(
                index, ref_kind, blob.get(field),
                f"{path}.{field}", SCHEMA_ID, field_name=field,
            ))
        issues.extend(check_ref(
            index, RefKind.MUSCLE_TBL, blob.get("muscle_table"),
            f"{path}.muscle_table", SCHEMA_ID, field_name="muscle_table",
        ))
        issues.extend(check_ref(
            index, RefKind.CONSTIT_TBL, blob.get("constitution_table"),
            f"{path}.constitution_table", SCHEMA_ID, field_name="constitution_table",
        ))
        issues.extend(check_ref(
            index, RefKind.BODY_SCHEMA, blob.get("body_schema"),
            f"{path}.body_schema", SCHEMA_ID, field_name="body_schema",
        ))

    for field_name, seed_table in _APPEARANCE_TYPE_KEYS:
        block = blob.get(field_name)
        if isinstance(block, dict):
            issues.extend(_validate_appearance_type_map(
                block, f"{path}.{field_name}", seed_table, index, seed_index,
            ))

    terrain = blob.get("terrain_access")
    if isinstance(terrain, list) and index is not None:
        for j, cat in enumerate(terrain):
            if isinstance(cat, str):
                issues.extend(check_ref(
                    index, RefKind.TERRAIN_CAT, cat,
                    f"{path}.terrain_access[{j}]", SCHEMA_ID, field_name="terrain_category",
                ))

    return issues


def _validate_lifespan(spans: Any, path: str, seed_index) -> list[ValidationIssue]:
    if spans is None:
        return []
    if not isinstance(spans, list) or not spans:
        return [error(SCHEMA_ID, path, "INVALID_TYPE", "lifespan must be a non-empty array")]
    issues: list[ValidationIssue] = []
    parsed: list[tuple[int, int, int]] = []
    for i, span in enumerate(spans):
        sbase = f"{path}[{i}]"
        if not isinstance(span, dict):
            issues.append(error(SCHEMA_ID, sbase, "INVALID_ENTRY", "lifespan entry must be an object"))
            continue
        start = span.get("from")
        end = span.get("to")
        if not isinstance(start, int) or isinstance(start, bool):
            issues.append(error(SCHEMA_ID, f"{sbase}.from", "MISSING_FIELD", "from is required"))
            continue
        if not isinstance(end, int) or isinstance(end, bool):
            issues.append(error(SCHEMA_ID, f"{sbase}.to", "MISSING_FIELD", "to is required"))
            continue
        if start > end:
            issues.append(error(
                SCHEMA_ID, sbase, "OUT_OF_RANGE", "lifespan from must be <= to",
            ))
        age_type = span.get("age_type")
        if age_type is not None and seed_index is not None and seed_index.keys("age_type"):
            if not isinstance(age_type, str) or not seed_index.has_seed("age_type", age_type):
                issues.append(error(
                    SCHEMA_ID, f"{sbase}.age_type", "UNKNOWN_REF",
                    f"unknown age_type {age_type!r}",
                ))
        parsed.append((start, end, i))

    parsed.sort(key=lambda t: t[0])
    for j in range(1, len(parsed)):
        prev_end = parsed[j - 1][1]
        cur_start = parsed[j][0]
        if cur_start <= prev_end:
            issues.append(error(
                SCHEMA_ID, path, "LIFESPAN_OVERLAP",
                "lifespan ranges must not overlap",
            ))
            break
        if cur_start != prev_end + 1:
            issues.append(error(
                SCHEMA_ID, path, "LIFESPAN_GAP",
                "lifespan ranges must be contiguous without gaps",
            ))
            break
    return issues


def _validate_measurement_range(block: Any, path: str) -> list[ValidationIssue]:
    if block is None:
        return []
    if not isinstance(block, dict):
        return [error(SCHEMA_ID, path, "INVALID_TYPE", "range must be an object")]
    issues: list[ValidationIssue] = []
    unit = block.get("system_measurement_unit")
    has_bounds = block.get("min") is not None or block.get("max") is not None
    if has_bounds and (not isinstance(unit, str) or not unit):
        issues.append(error(
            SCHEMA_ID, f"{path}.system_measurement_unit", "MISSING_FIELD",
            "system_measurement_unit is required when min/max present",
        ))
    for bound in ("min", "max"):
        val = block.get(bound)
        if val is not None and (not isinstance(val, (int, float)) or isinstance(val, bool)):
            issues.append(error(
                SCHEMA_ID, f"{path}.{bound}", "INVALID_TYPE", f"{bound} must be a number",
            ))
    min_v, max_v = block.get("min"), block.get("max")
    if isinstance(min_v, (int, float)) and isinstance(max_v, (int, float)) and min_v > max_v:
        issues.append(error(SCHEMA_ID, path, "OUT_OF_RANGE", "min must be <= max"))
    return issues


def _validate_appearance_type_map(
    block: dict[str, Any],
    path: str,
    seed_table: str,
    index,
    seed_index,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for type_key, entry in block.items():
        tpath = f"{path}.{type_key}"
        if seed_index is not None and seed_index.keys(seed_table):
            if not isinstance(type_key, str) or not seed_index.has_seed(seed_table, type_key):
                issues.append(error(
                    SCHEMA_ID, tpath, "UNKNOWN_REF",
                    f"unknown {seed_table} key {type_key!r}",
                ))
        if isinstance(entry, dict):
            issues.extend(_validate_colours_textures(entry, tpath, index))
            shapes = entry.get("shapes")
            if shapes is not None and not isinstance(shapes, list):
                issues.append(error(
                    SCHEMA_ID, f"{tpath}.shapes", "INVALID_TYPE", "shapes must be an array",
                ))
    return issues


def _validate_colours_textures(entry: dict[str, Any], path: str, index) -> list[ValidationIssue]:
    if index is None:
        return []
    issues: list[ValidationIssue] = []
    for field, ref_kind in (("colours", RefKind.COLOUR), ("textures", RefKind.TEXTURE)):
        vals = entry.get(field)
        if vals is None:
            continue
        if not isinstance(vals, list):
            issues.append(error(SCHEMA_ID, f"{path}.{field}", "INVALID_TYPE", f"{field} must be an array"))
            continue
        for j, val in enumerate(vals):
            if isinstance(val, str):
                issues.extend(check_ref(
                    index, ref_kind, val, f"{path}.{field}[{j}]",
                    SCHEMA_ID, field_name=field[:-1],
                ))
    return issues
