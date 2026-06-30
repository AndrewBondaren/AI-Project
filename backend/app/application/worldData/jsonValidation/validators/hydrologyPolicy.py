"""SCH-WORLD-HYDROLOGY — docs/tz_json_validation.md JV-3."""

from __future__ import annotations

from typing import Any

from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import check_ref

SCHEMA_ID = "SCH-WORLD-HYDROLOGY"

_BAND_SECTIONS = (
    ("default_rivers", "world.hydrology.default_rivers.bands"),
    ("default_lakes", "world.hydrology.default_lakes.bands"),
    ("default_seas", "world.hydrology.default_seas.bands"),
)


class HydrologyPolicyValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.WORLD})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors or ctx.index is None:
            return
        world = _world_blob(ctx)
        if world is None:
            return
        ctx.issues.extend(collect_hydrology_issues(world, ctx.index))


def _world_blob(ctx: ValidationContext) -> dict[str, Any] | None:
    bundle = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    if not isinstance(bundle, dict):
        return None
    world = bundle.get("world")
    return world if isinstance(world, dict) else None


def collect_hydrology_issues(world: dict[str, Any], index) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    hydrology = world.get("hydrology")
    if hydrology is None:
        return issues
    if not isinstance(hydrology, dict):
        return [error(SCHEMA_ID, "world.hydrology", "INVALID_TYPE", "hydrology must be an object")]

    shore = hydrology.get("default_shore")
    if isinstance(shore, dict):
        issues.extend(check_ref(
            index, RefKind.TERRAIN, shore.get("system_terrain"),
            "world.hydrology.default_shore.system_terrain", SCHEMA_ID, field_name="system_terrain",
        ))
        issues.extend(check_ref(
            index, RefKind.MATERIAL, shore.get("system_material"),
            "world.hydrology.default_shore.system_material", SCHEMA_ID, field_name="system_material",
        ))

    for section_key, path_prefix in _BAND_SECTIONS:
        section = hydrology.get(section_key)
        if not isinstance(section, dict):
            continue
        bands = section.get("bands")
        if bands is None:
            continue
        if not isinstance(bands, dict):
            issues.append(error(
                SCHEMA_ID, path_prefix, "INVALID_TYPE", "bands must be an object",
            ))
            continue
        issues.extend(_check_bands(bands, path_prefix))

    rivers = hydrology.get("default_rivers")
    if isinstance(rivers, dict):
        tc = rivers.get("type_classify")
        if isinstance(tc, dict):
            issues.extend(_check_type_classify(tc))

    return issues


def _check_bands(bands: dict[str, Any], path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    min_v = bands.get("min")
    max_v = bands.get("max")
    if min_v is not None and (not isinstance(min_v, int) or isinstance(min_v, bool) or not 1 <= min_v <= 99):
        issues.append(error(SCHEMA_ID, f"{path}.min", "OUT_OF_RANGE", "bands.min must be an integer 1..99"))
    if max_v is not None and (not isinstance(max_v, int) or isinstance(max_v, bool) or not 1 <= max_v <= 99):
        issues.append(error(SCHEMA_ID, f"{path}.max", "OUT_OF_RANGE", "bands.max must be an integer 1..99"))
    if isinstance(min_v, int) and isinstance(max_v, int) and not isinstance(min_v, bool) and not isinstance(max_v, bool):
        if min_v > max_v:
            issues.append(error(
                SCHEMA_ID, path, "OUT_OF_RANGE", "bands.max must be >= bands.min",
            ))
    return issues


def _check_type_classify(tc: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    base = "world.hydrology.default_rivers.type_classify"

    frac = tc.get("path_mountain_fraction")
    if frac is not None and (not isinstance(frac, (int, float)) or isinstance(frac, bool) or frac < 0 or frac > 1):
        issues.append(error(
            SCHEMA_ID, f"{base}.path_mountain_fraction", "OUT_OF_RANGE",
            "path_mountain_fraction must be between 0 and 1",
        ))

    steep = tc.get("mountain_bed_steepness_factor")
    if steep is not None and (not isinstance(steep, (int, float)) or isinstance(steep, bool) or steep <= 0):
        issues.append(error(
            SCHEMA_ID, f"{base}.mountain_bed_steepness_factor", "OUT_OF_RANGE",
            "mountain_bed_steepness_factor must be > 0",
        ))

    foothill = tc.get("foothill_gradient_threshold")
    if foothill is not None and (not isinstance(foothill, (int, float)) or isinstance(foothill, bool) or foothill < 0):
        issues.append(error(
            SCHEMA_ID, f"{base}.foothill_gradient_threshold", "OUT_OF_RANGE",
            "foothill_gradient_threshold must be >= 0",
        ))

    return issues
