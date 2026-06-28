import math

from app.application.worldData.generators.climate.climateAnchor import (
    AnchorSource,
    ClimateAnchorPoint,
)
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climateGeneratorService import (
    ClimateGeneratorService,
    SurfaceClimateSample,
)
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.registry import profile_for
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

DEFAULT_LOCAL_INFLUENCE_FRACTION = 0.1
LOCAL_INFLUENCE_BLEND_OUTER     = 0.2   # outer 20% of radius — temp smoothstep only


def _dist(gx: int, gy: int, anchor: ClimateAnchorPoint) -> float:
    return math.hypot(gx - anchor.gx, gy - anchor.gy)


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _influence_fraction(world: World) -> float:
    if world.climate_local_influence_fraction is not None:
        return world.climate_local_influence_fraction
    return DEFAULT_LOCAL_INFLUENCE_FRACTION


def _modifiers(field: ClimateAnchorField) -> list[ClimateAnchorPoint]:
    return [
        a for a in field.anchors
        if a.source in (AnchorSource.MANUAL, AnchorSource.AUTO)
    ]


def _sample_from_anchor(world: World, anchor: ClimateAnchorPoint) -> SurfaceClimateSample:
    profile = profile_for(world, anchor.system_climate_zone)
    return SurfaceClimateSample(
        system_climate_zone=profile.system_climate,
        zone_location_uid=anchor.location_uid,
        typical_elevation_z=profile.typical_elevation_z,
    )


def _pole_base_temperature(world: World, pole_sample: SurfaceClimateSample) -> int:
    if pole_sample.base_temperature_override is not None:
        return pole_sample.base_temperature_override
    return profile_for(world, pole_sample.system_climate_zone).base_temperature


def _influence_radius(
    world: World,
    bbox_diagonal: float,
    nearest: ClimateAnchorPoint,
    modifiers: list[ClimateAnchorPoint],
    gx: int,
    gy: int,
) -> float:
    base_r = bbox_diagonal * _influence_fraction(world)
    if len(modifiers) <= 1:
        return base_r

    others = [m for m in modifiers if m is not nearest]
    second = min(_dist(gx, gy, m) for m in others)
    return min(base_r, second / 2.0)


def resolve_tier_sample(
    svc: ClimateGeneratorService,
    world: World,
    uid_map: dict[str, NamedLocation],
    pole_field: ClimatePoleField,
    local_field: ClimateAnchorField,
    gx: int,
    gy: int,
) -> SurfaceClimateSample:
    """
    Tier 1 pole base; tier 2 MANUAL/AUTO override within world-relative radius.
    ADMIN anchors skipped when pole tier is active. Temp smoothstep in outer blend band.
    """
    pole_sample = svc.sample_at_pole_field(world, pole_field, gx, gy)
    modifiers   = _modifiers(local_field)

    if not modifiers:
        return pole_sample

    bbox = pole_field.bbox
    if bbox is None:
        return pole_sample

    nearest = min(modifiers, key=lambda m: _dist(gx, gy, m))
    dist    = _dist(gx, gy, nearest)
    radius  = _influence_radius(world, bbox.diagonal(), nearest, modifiers, gx, gy)

    if dist > radius:
        return pole_sample

    local_sample = _sample_from_anchor(world, nearest)
    inner        = radius * (1.0 - LOCAL_INFLUENCE_BLEND_OUTER)

    if dist <= inner:
        return local_sample

    local_base = profile_for(world, local_sample.system_climate_zone).base_temperature
    pole_base  = _pole_base_temperature(world, pole_sample)
    band       = radius - inner
    t          = _smoothstep((dist - inner) / band) if band > 0 else 1.0
    blended    = round(local_base + (pole_base - local_base) * t)

    return SurfaceClimateSample(
        system_climate_zone=local_sample.system_climate_zone,
        zone_location_uid=local_sample.zone_location_uid,
        typical_elevation_z=local_sample.typical_elevation_z,
        base_temperature_override=blended,
    )
