from app.application.worldData.generators.climate.climateAnchor import (
    AnchorSource,
    ClimateAnchorPoint,
)
from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climateGeneratorService import (
    ClimateGeneratorService,
    SurfaceClimateSample,
)
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.climate.math import dist_euclidean, smoothstep
from app.application.worldData.generators.climate.registry import profile_for
from app.dataModel.climate.climateAnchorInfluenceDefaults import (
    LOCAL_INFLUENCE_BLEND_OUTER,
    local_influence_fraction,
)
from app.application.jsonValidation import climate_scalars
from app.db.models.world import World


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


def _influence_diagonal(
    pole_field: ClimatePoleField,
    modifiers: list[ClimateAnchorPoint],
    world_uid: str | None = None,
) -> float | None:
    if pole_field.bbox is not None:
        return pole_field.bbox.diagonal()
    if not modifiers:
        return None
    if world_uid:
        warn_once(
            world_uid,
            "tier_modifier_bbox_fallback",
            "tier resolve | world=%s pole bbox missing; using modifier span for influence radius",
        )
    gx = [m.gx for m in modifiers]
    gy = [m.gy for m in modifiers]
    w  = max(1, max(gx) - min(gx) + 1)
    h  = max(1, max(gy) - min(gy) + 1)
    return dist_euclidean(0, 0, w, h)


def _influence_radius(
    world: World,
    bbox_diagonal: float,
    nearest: ClimateAnchorPoint,
    modifiers: list[ClimateAnchorPoint],
    gx: int,
    gy: int,
) -> float:
    base_r = bbox_diagonal * local_influence_fraction(
        climate_scalars(world).climate_local_influence_fraction,
    )
    if len(modifiers) <= 1:
        return base_r

    others = [m for m in modifiers if m is not nearest]
    second = min(dist_euclidean(gx, gy, m.gx, m.gy) for m in others)
    return min(base_r, second / 2.0)


def resolve_tier_sample(
    svc: ClimateGeneratorService,
    world: World,
    pole_field: ClimatePoleField,
    local_field: ClimateAnchorField,
    gx: int,
    gy: int,
) -> SurfaceClimateSample:
    """
    Tier 1 pole base; tier 2 MANUAL/AUTO override within world-relative radius.
    ADMIN anchors skipped. Temp smoothstep in outer blend band.
    """
    pole_sample = svc.sample_at_pole_field(world, pole_field, gx, gy)
    modifiers   = _modifiers(local_field)

    if not modifiers:
        return pole_sample

    diagonal = _influence_diagonal(pole_field, modifiers, world.world_uid)
    if diagonal is None:
        return pole_sample

    nearest = min(modifiers, key=lambda m: dist_euclidean(gx, gy, m.gx, m.gy))
    dist    = dist_euclidean(gx, gy, nearest.gx, nearest.gy)
    radius  = _influence_radius(world, diagonal, nearest, modifiers, gx, gy)

    if dist > radius:
        return pole_sample

    local_sample = _sample_from_anchor(world, nearest)
    inner        = radius * (1.0 - LOCAL_INFLUENCE_BLEND_OUTER)

    if dist <= inner:
        return local_sample

    local_base = profile_for(world, local_sample.system_climate_zone).base_temperature
    pole_base  = _pole_base_temperature(world, pole_sample)
    band       = radius - inner
    t          = smoothstep((dist - inner) / band) if band > 0 else 1.0
    blended    = round(local_base + (pole_base - local_base) * t)

    return SurfaceClimateSample(
        system_climate_zone=local_sample.system_climate_zone,
        zone_location_uid=local_sample.zone_location_uid,
        typical_elevation_z=local_sample.typical_elevation_z,
        base_temperature_override=blended,
    )
