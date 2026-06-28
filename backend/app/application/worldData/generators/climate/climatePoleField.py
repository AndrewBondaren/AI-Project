import math
from dataclasses import dataclass

from app.application.worldData.generators.climate.climatePole import (
    POLE_BLEND_EPS,
    POLE_BLEND_POWER,
    ClimatePolePoint,
)
from app.application.worldData.generators.climate.climateZone import ClimateZone
from app.application.worldData.generators.climate.math import dist_euclidean, smoothstep
from app.application.worldData.generators.climate.registry import profile_for
from app.db.models.world import World


@dataclass(frozen=True)
class GridBBox:
    x_min: int
    x_max: int
    y_min: int
    y_max: int

    def diagonal(self) -> float:
        w = max(1, self.x_max - self.x_min)
        h = max(1, self.y_max - self.y_min)
        return math.hypot(w, h)


@dataclass(frozen=True)
class PoleClimateSample:
    system_climate_zone:       str
    zone_location_uid:         str | None
    typical_elevation_z:       int
    base_temperature_override: int | None


@dataclass(frozen=True)
class ClimatePoleField:
    """Tier-1 pole climate — inverse-distance blend (N≥2) or fade to default (N=1)."""

    poles: tuple[ClimatePolePoint, ...]
    bbox:  GridBBox | None = None

    def is_empty(self) -> bool:
        return not self.poles

    def sample(self, world: World, gx: int, gy: int) -> PoleClimateSample:
        default_zone = world.default_climate_zone or ClimateZone.TEMPERATE
        default_prof = profile_for(world, default_zone)

        if not self.poles:
            return PoleClimateSample(
                system_climate_zone=default_prof.system_climate,
                zone_location_uid=None,
                typical_elevation_z=default_prof.typical_elevation_z,
                base_temperature_override=None,
            )

        if len(self.poles) == 1:
            return self._sample_single(world, gx, gy, self.poles[0], default_zone, default_prof)

        return self._sample_blend(world, gx, gy, default_zone, default_prof)

    def _sample_single(
        self,
        world: World,
        gx: int,
        gy: int,
        pole: ClimatePolePoint,
        default_zone: str,
        default_prof,
    ) -> PoleClimateSample:
        pole_prof = profile_for(world, pole.system_climate_zone)
        bbox      = self.bbox
        if bbox is None:
            return PoleClimateSample(
                system_climate_zone=pole_prof.system_climate,
                zone_location_uid=pole.location_uid,
                typical_elevation_z=pole_prof.typical_elevation_z,
                base_temperature_override=pole.base_temperature,
            )

        dist  = dist_euclidean(gx, gy, pole.gx, pole.gy)
        denom = max(1.0, bbox.diagonal() * 0.5)
        t     = smoothstep(dist / denom)

        temp = round(pole.base_temperature + (default_prof.base_temperature - pole.base_temperature) * t)
        elev = round(
            pole_prof.typical_elevation_z
            + (default_prof.typical_elevation_z - pole_prof.typical_elevation_z) * t
        )
        zone = pole_prof.system_climate if t < 0.5 else default_zone

        return PoleClimateSample(
            system_climate_zone=zone,
            zone_location_uid=pole.location_uid if t < 0.5 else None,
            typical_elevation_z=elev,
            base_temperature_override=temp,
        )

    def _sample_blend(
        self,
        world: World,
        gx: int,
        gy: int,
        default_zone: str,
        default_prof,
    ) -> PoleClimateSample:
        weights: list[float] = []
        for pole in self.poles:
            d = dist_euclidean(gx, gy, pole.gx, pole.gy)
            weights.append(pole.weight / (d + POLE_BLEND_EPS) ** POLE_BLEND_POWER)

        total = sum(weights)
        if total <= 0:
            return PoleClimateSample(
                system_climate_zone=default_prof.system_climate,
                zone_location_uid=None,
                typical_elevation_z=default_prof.typical_elevation_z,
                base_temperature_override=None,
            )

        temp = sum(w * p.base_temperature for w, p in zip(weights, self.poles)) / total

        best_idx = max(range(len(weights)), key=lambda i: weights[i])
        best     = self.poles[best_idx]
        prof     = profile_for(world, best.system_climate_zone)

        return PoleClimateSample(
            system_climate_zone=prof.system_climate,
            zone_location_uid=best.location_uid,
            typical_elevation_z=prof.typical_elevation_z,
            base_temperature_override=round(temp),
        )
