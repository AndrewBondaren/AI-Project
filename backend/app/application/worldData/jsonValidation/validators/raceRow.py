"""SCH-RACE-ROW — docs/tz_json_validation.md JV-8."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.registries.wireEnums import SystemGender
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import collect_duplicate_uids

SCHEMA_ID = "SCH-RACE-ROW"

_GENDER_COLUMNS = frozenset(m.value for m in SystemGender)


class RaceRowValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.RACES})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors:
            return
        races = _races(ctx)
        if races is None:
            return
        ctx.issues.extend(collect_race_row_issues(races))


def _races(ctx: ValidationContext) -> list[Any] | None:
    blob = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    if not isinstance(blob, dict):
        return None
    races = blob.get("races")
    return races if isinstance(races, list) else None


def collect_race_row_issues(races: list[Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(collect_duplicate_uids(races, "race_uid", "races", SCHEMA_ID))

    for i, row in enumerate(races):
        if not isinstance(row, dict):
            issues.append(error(
                SCHEMA_ID, f"races[{i}]", "INVALID_ROW", "race row must be an object",
            ))
            continue
        base = f"races[{i}]"
        for field in ("race_uid", "display_race", "created_at"):
            val = row.get(field)
            if not isinstance(val, str) or not val:
                issues.append(error(
                    SCHEMA_ID, f"{base}.{field}", "MISSING_FIELD", f"{field} is required",
                ))

        for gender in _GENDER_COLUMNS:
            blob = row.get(gender)
            if blob is None:
                continue
            if not isinstance(blob, dict):
                issues.append(error(
                    SCHEMA_ID, f"{base}.{gender}", "INVALID_TYPE",
                    f"{gender} must be an object or null",
                ))

        traits = row.get("race_traits")
        if traits is not None and not isinstance(traits, dict):
            issues.append(error(
                SCHEMA_ID, f"{base}.race_traits", "INVALID_TYPE", "race_traits must be an object",
            ))

    return issues
