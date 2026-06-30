"""N1-S schema normalize — docs/tz_json_validation.md §0 N1-S, JV-1."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.types import ValidationIssue

N1S_MAP_NORMALIZE_FIELDS = ("stat_schema", "skill_schema", "resist_schema")


def _dup_issue(path: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(
        schema_id="N1-S-normalize",
        path=path,
        code=code,
        message=message,
    )


def normalize_n1s_field(
    field_name: str,
    value: Any,
) -> tuple[Any, list[ValidationIssue]]:
    path_prefix = f"world.{field_name}"
    if value is None:
        return value, []
    if isinstance(value, list):
        return _validate_array(field_name, value)
    if isinstance(value, dict):
        if not value:
            return [], []
        rows: list[dict[str, Any]] = []
        issues: list[ValidationIssue] = []
        seen_names: set[str] = set()
        seen_aliases: set[str] = set()
        for key, entry in value.items():
            if not isinstance(key, str):
                issues.append(_dup_issue(
                    path_prefix,
                    "INVALID_MAP_KEY",
                    f"{field_name} map keys must be strings",
                ))
                continue
            if not isinstance(entry, dict):
                issues.append(_dup_issue(
                    f"{path_prefix}.{key}",
                    "INVALID_ENTRY",
                    f"{field_name}[{key!r}] must be an object",
                ))
                continue
            row = dict(entry)
            row["system_name"] = key
            row_issues = _check_row_uniques(
                field_name, row, seen_names, seen_aliases, map_key=key,
            )
            issues.extend(row_issues)
            rows.append(row)
        return rows, issues
    return value, [
        _dup_issue(path_prefix, "INVALID_L2", f"{field_name} must be a JSON object or array"),
    ]


def _validate_array(
    field_name: str,
    value: list[Any],
) -> tuple[list[Any], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    seen_names: set[str] = set()
    seen_aliases: set[str] = set()
    for i, entry in enumerate(value):
        if not isinstance(entry, dict):
            issues.append(_dup_issue(
                f"world.{field_name}[{i}]",
                "INVALID_ENTRY",
                f"{field_name}[{i}] must be an object",
            ))
            continue
        issues.extend(_check_row_uniques(field_name, entry, seen_names, seen_aliases, index=i))
    return value, issues


def _check_row_uniques(
    field_name: str,
    row: dict[str, Any],
    seen_names: set[str],
    seen_aliases: set[str],
    *,
    index: int | None = None,
    map_key: str | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if map_key is not None:
        base = f"world.{field_name}.{map_key}"
    elif index is not None:
        base = f"world.{field_name}[{index}]"
    else:
        base = f"world.{field_name}.{row.get('system_name', '?')}"

    name = row.get("system_name")
    if not isinstance(name, str) or not name:
        issues.append(_dup_issue(base, "MISSING_SYSTEM_NAME", "system_name is required"))
        return issues

    if name in seen_names:
        issues.append(_dup_issue(base, "DUP_SYSTEM_NAME", f"duplicate system_name {name!r}"))
    seen_names.add(name)

    alias = row.get("alias")
    if alias is not None:
        if not isinstance(alias, str) or not alias:
            issues.append(_dup_issue(base, "INVALID_ALIAS", "alias must be a non-empty string"))
        elif alias in seen_aliases:
            issues.append(_dup_issue(f"{base}.alias", "DUP_ALIAS", f"duplicate alias {alias!r}"))
        else:
            seen_aliases.add(alias)
    return issues


def normalize_world_n1s(world: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for field_name in N1S_MAP_NORMALIZE_FIELDS:
        if field_name not in world:
            continue
        normalized, field_issues = normalize_n1s_field(field_name, world[field_name])
        world[field_name] = normalized
        issues.extend(field_issues)
    return issues
