"""Shared row validation helpers."""

from __future__ import annotations

from typing import Any, Literal

from app.application.shared.wire import WireEnumError, parse_enum
from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.worldData.jsonValidation.types import ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error


def collect_duplicate_uids(
    rows: list[Any],
    uid_field: str,
    path_prefix: str,
    schema_id: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        uid = row.get(uid_field)
        if not isinstance(uid, str) or not uid:
            issues.append(error(
                schema_id, f"{path_prefix}[{i}].{uid_field}",
                "MISSING_FIELD", f"{uid_field} is required",
            ))
            continue
        if uid in seen:
            issues.append(error(
                schema_id, f"{path_prefix}[{i}].{uid_field}",
                "DUP_UID", f"duplicate {uid_field} {uid!r}",
            ))
        seen.add(uid)
    return issues


def check_fk(
    value: Any,
    valid_uids: set[str],
    path: str,
    schema_id: str,
    *,
    field_name: str,
) -> list[ValidationIssue]:
    if value is None:
        return []
    if not isinstance(value, str) or not value:
        return [error(schema_id, path, "INVALID_FK", f"{field_name} must be a non-empty string")]
    if value not in valid_uids:
        return [error(schema_id, path, "BROKEN_FK", f"unknown {field_name} {value!r}")]
    return []


def check_ref(
    index: WorldRegistryIndex,
    ref_kind: RefKind,
    value: Any,
    path: str,
    schema_id: str,
    *,
    field_name: str,
    severity: Literal["error", "warn"] = "error",
) -> list[ValidationIssue]:
    if value is None or value == "":
        return []
    if not isinstance(value, str):
        return [error(schema_id, path, "INVALID_REF", f"{field_name} must be a string")]
    known = index.keys(ref_kind)
    if not known:
        return []
    if not index.has_ref(ref_kind, value):
        return [ValidationIssue(
            schema_id=schema_id,
            path=path,
            code="UNKNOWN_REF",
            message=f"unknown {field_name} {value!r} (not in {ref_kind.value} registry)",
            severity=severity,
        )]
    return []


def check_wire_enum(
    enum_cls: type,
    value: Any,
    path: str,
    schema_id: str,
    *,
    field_name: str,
) -> list[ValidationIssue]:
    if value is None:
        return []
    if not isinstance(value, str):
        return [error(schema_id, path, "INVALID_ENUM", f"{field_name} must be a string")]
    try:
        parse_enum(enum_cls, value, field=field_name)
    except WireEnumError as exc:
        return [error(schema_id, path, "UNKNOWN_ENUM", str(exc))]
    return []


def detect_parent_cycles(
    rows: list[dict[str, Any]],
    uid_field: str,
    parent_field: str,
    path_prefix: str,
    schema_id: str,
) -> list[ValidationIssue]:
    by_uid = {
        row[uid_field]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get(uid_field), str)
    }
    issues: list[ValidationIssue] = []
    for uid, row in by_uid.items():
        visited: set[str] = set()
        current: str | None = uid
        while current:
            if current in visited:
                issues.append(error(
                    schema_id, f"{path_prefix}.{uid}.{parent_field}",
                    "PARENT_CYCLE", f"parent cycle detected at {uid!r}",
                ))
                break
            visited.add(current)
            parent = by_uid.get(current, {}).get(parent_field)
            if parent is None:
                break
            if not isinstance(parent, str):
                break
            current = parent
    return issues
