"""SCH-SEED-BUNDLE — N1-G seed tables — docs/tz_json_validation.md T6."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import collect_duplicate_uids
from app.application.worldData.seedService import ALLOWED_SEED_TABLES

SCHEMA_ID = "SCH-SEED-BUNDLE"


def seed_pk_field(table: str) -> str:
    return f"system_{table}"


def seed_display_field(table: str) -> str:
    return f"display_{table}"


class SeedTableValidator:
    schema_id = SCHEMA_ID
    sections: frozenset[SectionKey] = frozenset()

    def validate(self, ctx: ValidationContext) -> None:
        from app.application.worldData.jsonValidation.types import ValidationKind

        if ctx.request.kind != ValidationKind.SEED:
            return
        if not isinstance(ctx.normalized, dict):
            ctx.issues.append(error(
                SCHEMA_ID, "$", "INVALID_TYPE", "seed payload must be a JSON object",
            ))
            return
        ctx.issues.extend(collect_seed_bundle_issues(ctx.normalized))


def collect_seed_bundle_issues(data: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for table, rows in data.items():
        if not isinstance(table, str):
            issues.append(error(
                SCHEMA_ID, "$", "INVALID_KEY", "seed bundle keys must be table names",
            ))
            continue
        if table not in ALLOWED_SEED_TABLES:
            issues.append(error(
                SCHEMA_ID, table, "UNKNOWN_TABLE",
                f"unknown seed table {table!r}",
            ))
            continue
        issues.extend(_validate_table_rows(table, rows))
    return issues


def collect_seed_table_issues(table: str, rows: list[Any]) -> list[ValidationIssue]:
    if table not in ALLOWED_SEED_TABLES:
        return [error(
            SCHEMA_ID, table, "UNKNOWN_TABLE",
            f"unknown seed table {table!r}",
        )]
    return _validate_table_rows(table, rows)


def _validate_table_rows(table: str, rows: Any) -> list[ValidationIssue]:
    path = table
    if not isinstance(rows, list):
        return [error(SCHEMA_ID, path, "INVALID_TYPE", f"{table} must be an array")]
    issues: list[ValidationIssue] = []
    pk_field = seed_pk_field(table)
    display_field = seed_display_field(table)
    issues.extend(collect_duplicate_uids(rows, pk_field, table, SCHEMA_ID))

    for i, row in enumerate(rows):
        base = f"{table}[{i}]"
        if not isinstance(row, dict):
            issues.append(error(SCHEMA_ID, base, "INVALID_ROW", "seed row must be an object"))
            continue
        pk = row.get(pk_field)
        if not isinstance(pk, str) or not pk:
            issues.append(error(
                SCHEMA_ID, f"{base}.{pk_field}", "MISSING_FIELD",
                f"{pk_field} is required",
            ))
        display = row.get(display_field)
        if not isinstance(display, str) or not display:
            issues.append(error(
                SCHEMA_ID, f"{base}.{display_field}", "MISSING_FIELD",
                f"{display_field} is required",
            ))
        if table == "social_status":
            weight = row.get("social_status_weight")
            if weight is not None and (
                not isinstance(weight, int) or isinstance(weight, bool)
            ):
                issues.append(error(
                    SCHEMA_ID, f"{base}.social_status_weight", "INVALID_TYPE",
                    "social_status_weight must be an integer",
                ))
    return issues
