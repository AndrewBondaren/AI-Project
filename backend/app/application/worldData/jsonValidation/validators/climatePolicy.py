"""SCH-WORLD-CLIMATE-POLICY — docs/tz_json_validation.md JV-3."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.registries.wireEnums import (
    ClimatePoleMode,
    ClimatePolePreset,
    MeasurementSystem,
    SeasonKey,
)
from app.application.worldData.jsonValidation.index.refKind import RefKind
from app.application.worldData.jsonValidation.types import SectionKey, ValidationContext, ValidationIssue
from app.application.worldData.jsonValidation.validators._issues import error
from app.application.worldData.jsonValidation.validators._rowHelpers import (
    check_ref,
    check_wire_enum,
)

SCHEMA_ID = "SCH-WORLD-CLIMATE-POLICY"


class ClimatePolicyValidator:
    schema_id = SCHEMA_ID
    sections = frozenset({SectionKey.WORLD})

    def validate(self, ctx: ValidationContext) -> None:
        if ctx.has_errors or ctx.index is None:
            return
        world = _world_blob(ctx)
        if world is None:
            return
        ctx.issues.extend(collect_climate_policy_issues(world, ctx.index))


def _world_blob(ctx: ValidationContext) -> dict[str, Any] | None:
    bundle = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
    if not isinstance(bundle, dict):
        return None
    world = bundle.get("world")
    return world if isinstance(world, dict) else None


def collect_climate_policy_issues(world: dict[str, Any], index) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    issues.extend(check_wire_enum(
        MeasurementSystem, world.get("measurement_system"),
        "world.measurement_system", SCHEMA_ID, field_name="measurement_system",
    ))
    issues.extend(check_wire_enum(
        ClimatePoleMode, world.get("climate_pole_mode"),
        "world.climate_pole_mode", SCHEMA_ID, field_name="climate_pole_mode",
    ))
    issues.extend(check_wire_enum(
        ClimatePolePreset, world.get("climate_pole_preset"),
        "world.climate_pole_preset", SCHEMA_ID, field_name="climate_pole_preset",
    ))
    issues.extend(check_ref(
        index, RefKind.CLIMATE, world.get("default_climate_zone"),
        "world.default_climate_zone", SCHEMA_ID, field_name="default_climate_zone",
    ))
    issues.extend(check_ref(
        index, RefKind.LIQUID, world.get("precipitation_liquid"),
        "world.precipitation_liquid", SCHEMA_ID, field_name="precipitation_liquid",
    ))

    peak_min = world.get("climate_temperature_peak_min")
    peak_max = world.get("climate_temperature_peak_max")
    if peak_min is not None and peak_max is not None:
        if not isinstance(peak_min, int) or isinstance(peak_min, bool):
            issues.append(error(
                SCHEMA_ID, "world.climate_temperature_peak_min", "INVALID_TYPE",
                "climate_temperature_peak_min must be an integer",
            ))
        elif not isinstance(peak_max, int) or isinstance(peak_max, bool):
            issues.append(error(
                SCHEMA_ID, "world.climate_temperature_peak_max", "INVALID_TYPE",
                "climate_temperature_peak_max must be an integer",
            ))
        elif peak_min > peak_max:
            issues.append(error(
                SCHEMA_ID, "world.climate_temperature_peak_min", "OUT_OF_RANGE",
                "climate_temperature_peak_min must be <= climate_temperature_peak_max",
            ))

    z_min = world.get("z_min")
    z_max = world.get("z_max")
    if z_min is not None and z_max is not None:
        if isinstance(z_min, int) and isinstance(z_max, int) and not isinstance(z_min, bool) and not isinstance(z_max, bool):
            if z_min > z_max:
                issues.append(error(
                    SCHEMA_ID, "world.z_min", "OUT_OF_RANGE", "z_min must be <= z_max",
                ))

    fraction = world.get("climate_local_influence_fraction")
    if fraction is not None:
        if not isinstance(fraction, (int, float)) or isinstance(fraction, bool):
            issues.append(error(
                SCHEMA_ID, "world.climate_local_influence_fraction", "INVALID_TYPE",
                "climate_local_influence_fraction must be a number",
            ))
        elif fraction < 0 or fraction > 1:
            issues.append(error(
                SCHEMA_ID, "world.climate_local_influence_fraction", "OUT_OF_RANGE",
                "climate_local_influence_fraction should be between 0 and 1",
            ))

    offsets = world.get("season_temp_offsets")
    if offsets is not None:
        if not isinstance(offsets, dict):
            issues.append(error(
                SCHEMA_ID, "world.season_temp_offsets", "INVALID_TYPE",
                "season_temp_offsets must be an object",
            ))
        else:
            for key, value in offsets.items():
                path = f"world.season_temp_offsets.{key}"
                issues.extend(check_wire_enum(
                    SeasonKey, key, path, SCHEMA_ID, field_name="season key",
                ))
                if not isinstance(value, int) or isinstance(value, bool):
                    issues.append(error(
                        SCHEMA_ID, path, "INVALID_TYPE",
                        "season offset must be an integer (°C)",
                    ))

    return issues
