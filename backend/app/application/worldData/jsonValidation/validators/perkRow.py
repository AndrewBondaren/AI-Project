"""SCH-PERK-ROW — docs/tz_json_validation.md, project_data_storage_tz.md § Перки."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import (
    check_ref,
    collect_duplicate_uids,
)

SCHEMA_ID = "SCH-PERK-ROW"

_REQUIRED_STRINGS = ("perk_uid", "system_name", "display_name")
_OPTIONAL_STRINGS = (
    "system_description",
    "display_description",
    "display_rank_value",
    "display_tags",
    "system_condition",
    "display_condition",
)
_OPTIONAL_LISTS = ("system_tags", "terrain_access")


class PerkRowValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.PERKS})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors:
            return
        perks = _perks(ctx)
        if perks is None:
            return
        ctx.issues.extend(collect_perk_row_issues(perks, ctx.index))


def _perks(ctx: ValidationContext) -> list[Any] | None:
    blob = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    if not isinstance(blob, dict):
        return None
    perks = blob.get("perks")
    return perks if isinstance(perks, list) else None


def collect_perk_row_issues(
    perks: list[Any],
    index=None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(collect_duplicate_uids(perks, "perk_uid", "perks", SCHEMA_ID))
    issues.extend(_duplicate_system_names(perks))

    for i, row in enumerate(perks):
        if not isinstance(row, dict):
            issues.append(error(
                SCHEMA_ID, f"perks[{i}]", "INVALID_ROW", "perk row must be an object",
            ))
            continue
        base = f"perks[{i}]"
        for field in _REQUIRED_STRINGS:
            val = row.get(field)
            if not isinstance(val, str) or not val:
                issues.append(error(
                    SCHEMA_ID, f"{base}.{field}", "MISSING_FIELD", f"{field} is required",
                ))

        for field in _OPTIONAL_STRINGS:
            val = row.get(field)
            if val is not None and not isinstance(val, str):
                issues.append(error(
                    SCHEMA_ID, f"{base}.{field}", "INVALID_TYPE", f"{field} must be a string",
                ))

        for field in _OPTIONAL_LISTS:
            val = row.get(field)
            if val is None:
                continue
            if not isinstance(val, list):
                issues.append(error(
                    SCHEMA_ID, f"{base}.{field}", "INVALID_TYPE", f"{field} must be an array",
                ))
                continue
            if field == "terrain_access" and index is not None:
                for j, cat in enumerate(val):
                    if isinstance(cat, str):
                        issues.extend(check_ref(
                            index, RefKind.TERRAIN_CAT, cat,
                            f"{base}.terrain_access[{j}]", SCHEMA_ID,
                            field_name="terrain_category",
                        ))
            if field == "system_tags" and index is not None:
                for j, tag in enumerate(val):
                    if isinstance(tag, str):
                        issues.extend(check_ref(
                            index, RefKind.TAG, tag,
                            f"{base}.system_tags[{j}]", SCHEMA_ID,
                            field_name="tag_ref", severity="warn",
                        ))

        issues.extend(_validate_rank_value(row.get("system_rank_value"), f"{base}.system_rank_value"))

    return issues


def _duplicate_system_names(perks: list[Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for i, row in enumerate(perks):
        if not isinstance(row, dict):
            continue
        name = row.get("system_name")
        if not isinstance(name, str) or not name:
            continue
        if name in seen:
            issues.append(error(
                SCHEMA_ID, f"perks[{i}].system_name", "DUP_KEY",
                f"duplicate system_name {name!r}",
            ))
        seen.add(name)
    return issues


def _validate_rank_value(block: Any, path: str) -> list[ValidationIssue]:
    if block is None:
        return []
    if not isinstance(block, list):
        return [error(SCHEMA_ID, path, "INVALID_TYPE", "system_rank_value must be an array")]
    issues: list[ValidationIssue] = []
    for i, entry in enumerate(block):
        base = f"{path}[{i}]"
        if not isinstance(entry, dict):
            issues.append(error(SCHEMA_ID, base, "INVALID_ENTRY", "rank entry must be an object"))
            continue
        rank = entry.get("rank")
        if rank is not None and not isinstance(rank, str):
            issues.append(error(
                SCHEMA_ID, f"{base}.rank", "INVALID_TYPE", "rank must be a string",
            ))
        value = entry.get("value")
        if value is None:
            continue
        if not isinstance(value, list) or len(value) != 2:
            issues.append(error(
                SCHEMA_ID, f"{base}.value", "INVALID_TYPE",
                "value must be a two-element [min, max] array",
            ))
            continue
        lo, hi = value[0], value[1]
        if not isinstance(lo, (int, float)) or isinstance(lo, bool):
            issues.append(error(SCHEMA_ID, f"{base}.value[0]", "INVALID_TYPE", "min must be a number"))
        if not isinstance(hi, (int, float)) or isinstance(hi, bool):
            issues.append(error(SCHEMA_ID, f"{base}.value[1]", "INVALID_TYPE", "max must be a number"))
        if (
            isinstance(lo, (int, float)) and not isinstance(lo, bool)
            and isinstance(hi, (int, float)) and not isinstance(hi, bool)
            and lo > hi
        ):
            issues.append(error(
                SCHEMA_ID, f"{base}.value", "OUT_OF_RANGE", "value min must be <= max",
            ))
    return issues
