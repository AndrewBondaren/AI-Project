"""Pure pole sampling from frozen profiles; one kernel for legacy and plans."""

from collections.abc import Mapping

from app.dataModel.registryKey import RegistryKey
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry

from app.application.worldData.generators.climate.math import dist_euclidean, smoothstep
from app.dataModel.climate.climatePoleBlendDefaults import ClimatePoleBlendDefaults
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.climatePoints import ClimateKey, ClimatePolePoint, PoleClimateSample
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.dataModel.spatial.grid.gridBBox import GridBBox


def sample_resolved_profiles(poles: tuple[ClimatePolePoint, ...], bbox: GridBBox | None,
                             default_zone: ClimateKey,
                             profiles: Mapping[ClimateKey, ClimateZoneProfile],
                             blend: ClimatePoleBlendDefaults, gx: GridX, gy: GridY) -> PoleClimateSample:
    """Legacy aliases retain their resolved profile key, without live lookups."""
    index = profiles
    default = index[default_zone]
    if not poles:
        return PoleClimateSample(system_climate_zone=RegistryKey[WorldClimateZoneRegistry](default.system_climate), zone_location_uid=None,
            typical_elevation_z=default.typical_elevation_z, base_temperature_override=None)
    if len(poles) == 1:
        pole = poles[0]
        profile = index[pole.system_climate_zone]
        if bbox is None:
            return PoleClimateSample(system_climate_zone=RegistryKey[WorldClimateZoneRegistry](profile.system_climate),
                zone_location_uid=pole.location_uid, typical_elevation_z=profile.typical_elevation_z,
                base_temperature_override=pole.base_temperature)
        distance = dist_euclidean(gx, gy, pole.gx, pole.gy)
        fade = smoothstep(distance / max(1.0, bbox.diagonal() * blend.single_pole_fade_diagonal_factor))
        return PoleClimateSample(
            system_climate_zone=RegistryKey[WorldClimateZoneRegistry](profile.system_climate) if fade < 0.5 else default_zone,
            zone_location_uid=pole.location_uid if fade < 0.5 else None,
            typical_elevation_z=round(profile.typical_elevation_z +
                (default.typical_elevation_z - profile.typical_elevation_z) * fade),
            base_temperature_override=round(pole.base_temperature +
                (default.base_temperature - pole.base_temperature) * fade))
    weights = [pole.weight / (dist_euclidean(gx, gy, pole.gx, pole.gy) + blend.eps) ** blend.power
               for pole in poles]
    total = sum(weights)
    if total <= 0:
        return PoleClimateSample(system_climate_zone=RegistryKey[WorldClimateZoneRegistry](default.system_climate), zone_location_uid=None,
            typical_elevation_z=default.typical_elevation_z, base_temperature_override=None)
    best = poles[max(range(len(weights)), key=lambda index: weights[index])]
    profile = index[best.system_climate_zone]
    return PoleClimateSample(system_climate_zone=RegistryKey[WorldClimateZoneRegistry](profile.system_climate),
        zone_location_uid=best.location_uid, typical_elevation_z=profile.typical_elevation_z,
        base_temperature_override=round(sum(weight * pole.base_temperature
            for weight, pole in zip(weights, poles)) / total))


class ClimatePlanSampler:
    @staticmethod
    def sample(plan: ClimateBasePlan, gx: GridX, gy: GridY) -> PoleClimateSample:
        profiles = {profile.key: ClimateZoneProfile.from_data(profile.key, profile.values)
                    for profile in plan.profiles}
        return ClimatePlanSampler.sample_prepared(plan, profiles, gx, gy)

    @staticmethod
    def sample_prepared(plan: ClimateBasePlan, profiles: Mapping[ClimateKey, ClimateZoneProfile],
                        gx: GridX, gy: GridY) -> PoleClimateSample:
        return sample_resolved_profiles(plan.poles, plan.bbox, plan.default_zone, profiles, plan.blend, gx, gy)

