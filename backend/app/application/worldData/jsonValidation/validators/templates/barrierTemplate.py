"""SCH-BARRIER-TEMPLATE — docs/tz_locations barrier_template_registry, JV-5."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import check_ref

SCHEMA_ID = "SCH-BARRIER-TEMPLATE"


def collect_barrier_template_issues(
    data: dict[str, Any],
    *,
    index=None,
    path_prefix: str = "",
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    base = path_prefix or "$"

    if not isinstance(data, dict):
        return [error(SCHEMA_ID, base, "INVALID_TYPE", "barrier template must be an object")]

    system_type = data.get("system_type") or data.get("system_name")
    path = f"{base}.system_type" if base != "$" else "system_type"
    if not isinstance(system_type, str) or not system_type:
        issues.append(error(SCHEMA_ID, path, "MISSING_FIELD", "system_type is required"))

    if index is not None and data.get("glossary_ref") is not None:
        issues.extend(check_ref(
            index, RefKind.LORE, data.get("glossary_ref"),
            f"{base}.glossary_ref", SCHEMA_ID, field_name="glossary_ref", severity="warn",
        ))

    issues.extend(_validate_min_max_block(data.get("height_levels"), f"{base}.height_levels"))
    issues.extend(_validate_min_max_block(data.get("gates"), f"{base}.gates"))

    material = data.get("wall_material")
    if isinstance(material, dict):
        pick = material.get("pick_from")
        if pick is not None:
            if not isinstance(pick, list):
                issues.append(error(
                    SCHEMA_ID, f"{base}.wall_material.pick_from", "INVALID_TYPE",
                    "pick_from must be an array",
                ))
            elif index is not None:
                for j, mat in enumerate(pick):
                    issues.extend(check_ref(
                        index, RefKind.MATERIAL, mat,
                        f"{base}.wall_material.pick_from[{j}]", SCHEMA_ID, field_name="material",
                    ))

    return issues


def _validate_min_max_block(block: Any, path: str) -> list[ValidationIssue]:
    if block is None:
        return []
    if not isinstance(block, dict):
        return [error(SCHEMA_ID, path, "INVALID_TYPE", f"{path.split('.')[-1]} must be an object")]
    issues: list[ValidationIssue] = []
    min_v = block.get("min")
    max_v = block.get("max")
    if min_v is not None and (not isinstance(min_v, int) or isinstance(min_v, bool) or min_v < 0):
        issues.append(error(SCHEMA_ID, f"{path}.min", "OUT_OF_RANGE", "min must be an integer >= 0"))
    if max_v is not None and (not isinstance(max_v, int) or isinstance(max_v, bool) or max_v < 0):
        issues.append(error(SCHEMA_ID, f"{path}.max", "OUT_OF_RANGE", "max must be an integer >= 0"))
    if isinstance(min_v, int) and isinstance(max_v, int) and not isinstance(min_v, bool) and not isinstance(max_v, bool):
        if min_v > max_v:
            issues.append(error(SCHEMA_ID, path, "OUT_OF_RANGE", "max must be >= min"))
    return issues
