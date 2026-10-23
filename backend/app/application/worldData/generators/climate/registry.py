from app.application.worldData.generators.climate.climateZone import (
    ClimateZoneProfile,
    enum_default_profile,
    fallback_profile,
)
from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.jsonValidation import climate_zones
from app.db.models.world import World
from app.application.jsonValidation.resolve import ResolveContext, report_issues
from app.dataModel.climate.climateZone.climateZoneEntry import ClimateZoneEntry
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
from app.dataModel.climate.enums.climateZone import ClimateZoneProfileData
from app.dataModel.climate.planning.climatePlan import ResolvedClimateProfile
from app.dataModel.climate.planning.climatePoints import ClimateKey
from app.dataModel.climate.planning.inputs.climateBaseInput import ManualPoleInput
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.registryKey import RegistryKey
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _int_or(value: int | None, default: int) -> int:
    return default if value is None else int(value)


def _entry_to_profile(entry: ClimateZoneEntry, fallback: ClimateZoneProfile) -> ClimateZoneProfile:
    return ClimateZoneProfile(
        system_climate=entry.system_climate,
        base_temperature=_int_or(entry.base_temperature, fallback.base_temperature),
        typical_elevation_z=_int_or(entry.typical_elevation_z, fallback.typical_elevation_z),
        base_rainfall=_int_or(entry.base_rainfall, fallback.base_rainfall),
        temperature_variance=_int_or(entry.temperature_variance, fallback.temperature_variance),
        rainfall_variance=_int_or(entry.rainfall_variance, fallback.rainfall_variance),
    )


def profile_for(world: World, system_climate: str) -> ClimateZoneProfile:
    """
    Resolve climate profile: world registry entry overrides enum defaults.
    Unknown keys fall back to TEMPERATE enum profile.
    """
    enum_default = enum_default_profile(system_climate)
    base = enum_default or fallback_profile()

    entry = climate_zones(world).entry_for(system_climate)
    if entry is not None:
        return _entry_to_profile(entry, base)

    if enum_default is None:
        warn_once(
            world.world_uid,
            f"unknown_climate:{system_climate}",
            "climate_zone profile | world=%s unknown system_climate=%s; using temperate defaults",
            system_climate,
        )

    return base


def resolve_base_profiles(default_zone: ClimateKey, manual_poles: tuple[ManualPoleInput, ...],
                          preset: ClimatePolePreset, registry: WorldClimateZoneRegistry,
                          ctx: ResolveContext) -> tuple[tuple[ResolvedClimateProfile, ...], tuple[PlanDiagnostic, ...]]:
    """Own required profile keys, value fallback and its diagnostic disposition."""
    keys = {default_zone, *(point.zone for point in manual_poles if point.zone is not None),
            *(spec.system_climate_zone for spec in preset.pole_specs())}
    profiles: list[ResolvedClimateProfile] = []
    diagnostics: list[PlanDiagnostic] = []
    for key in sorted(keys):
        fallback = enum_default_profile(key)
        entry = registry.entry_for(key)
        if entry is None and fallback is None:
            diagnostic = PlanDiagnostic(issue=FieldPathError(("climate_zone_registry", key),
                "unknown climate profile; using canonical fallback", code="unknown_climate"),
                disposition=PlanDiagnosticDisposition.FALLBACK)
            diagnostics.append(diagnostic)
            report_issues(ctx, (diagnostic.issue,))
        base = fallback if fallback is not None else fallback_profile()
        profile = base if entry is None else _entry_to_profile(entry, base)
        profiles.append(ResolvedClimateProfile(key=RegistryKey[WorldClimateZoneRegistry](key), values=ClimateZoneProfileData(
            base_temperature=profile.base_temperature, typical_elevation_z=profile.typical_elevation_z,
            base_rainfall=profile.base_rainfall, temperature_variance=profile.temperature_variance,
            rainfall_variance=profile.rainfall_variance)))
    return tuple(profiles), tuple(diagnostics)
