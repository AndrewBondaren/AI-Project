"""SCH-DISTRICT-TEMPLATE — docs/tz_city_generation.md §9, JV-5."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.registries.wireEnums import DistrictDensity, StreetLayout
from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import check_ref, check_wire_enum

SCHEMA_ID = "SCH-DISTRICT-TEMPLATE"

_REQUIRED_STRUCTURE_POSITIONS = frozenset({"center", "any"})
_PLACEMENT_TYPES = frozenset({
    "adjacent_terrain",
    "min_city_size",
    "economic_tier_min",
    "economic_tier_max",
    "requires_district_type",
    "excludes_district_type",
    "cell_zone",
})


def collect_district_template_issues(
    data: dict[str, Any],
    *,
    index=None,
    path_prefix: str = "",
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    base = path_prefix or "$"

    if not isinstance(data, dict):
        return [error(SCHEMA_ID, base, "INVALID_TYPE", "district template must be an object")]

    for field in ("system_name", "display_name", "district_type"):
        val = data.get(field)
        path = f"{base}.{field}" if base != "$" else field
        if not isinstance(val, str) or not val:
            issues.append(error(SCHEMA_ID, path, "MISSING_FIELD", f"{field} is required"))

    if data.get("street_layout") is not None:
        issues.extend(check_wire_enum(
            StreetLayout, data["street_layout"], f"{base}.street_layout", SCHEMA_ID,
            field_name="street_layout",
        ))
    if data.get("density") is not None:
        issues.extend(check_wire_enum(
            DistrictDensity, data["density"], f"{base}.density", SCHEMA_ID, field_name="density",
        ))

    max_per = data.get("max_per_city")
    if max_per is not None and (not isinstance(max_per, int) or isinstance(max_per, bool) or max_per < 1):
        issues.append(error(
            SCHEMA_ID, f"{base}.max_per_city", "OUT_OF_RANGE", "max_per_city must be an integer >= 1",
        ))

    conditions = data.get("placement_conditions")
    if conditions is not None:
        if not isinstance(conditions, list):
            issues.append(error(
                SCHEMA_ID, f"{base}.placement_conditions", "INVALID_TYPE",
                "placement_conditions must be an array",
            ))
        else:
            for i, cond in enumerate(conditions):
                if not isinstance(cond, dict):
                    continue
                ctype = cond.get("type")
                if not isinstance(ctype, str) or ctype not in _PLACEMENT_TYPES:
                    issues.append(error(
                        SCHEMA_ID, f"{base}.placement_conditions[{i}].type", "UNKNOWN_ENUM",
                        f"unknown placement condition type {ctype!r}",
                    ))

    required = data.get("required_structures")
    if required is not None:
        if not isinstance(required, list):
            issues.append(error(
                SCHEMA_ID, f"{base}.required_structures", "INVALID_TYPE",
                "required_structures must be an array",
            ))
        else:
            for i, req in enumerate(required):
                if not isinstance(req, dict):
                    continue
                rbase = f"{base}.required_structures[{i}]"
                if not isinstance(req.get("building_template"), str) or not req.get("building_template"):
                    issues.append(error(
                        SCHEMA_ID, f"{rbase}.building_template", "MISSING_FIELD",
                        "building_template is required",
                    ))
                elif index is not None:
                    issues.extend(check_ref(
                        index, RefKind.BUILDING_TPL, req["building_template"],
                        f"{rbase}.building_template", SCHEMA_ID, field_name="building_template",
                    ))
                count = req.get("count", 1)
                if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                    issues.append(error(
                        SCHEMA_ID, f"{rbase}.count", "OUT_OF_RANGE", "count must be an integer >= 1",
                    ))
                pos = req.get("position", "any")
                if pos not in _REQUIRED_STRUCTURE_POSITIONS:
                    issues.append(error(
                        SCHEMA_ID, f"{rbase}.position", "UNKNOWN_ENUM",
                        f"position must be one of: {', '.join(sorted(_REQUIRED_STRUCTURE_POSITIONS))}",
                    ))

    allowed = data.get("allowed_structure_types")
    if allowed is not None and not isinstance(allowed, list):
        issues.append(error(
            SCHEMA_ID, f"{base}.allowed_structure_types", "INVALID_TYPE",
            "allowed_structure_types must be an array",
        ))

    return issues
