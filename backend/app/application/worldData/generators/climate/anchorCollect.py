from app.application.worldData.generators.climate.climateAnchor import (
    ADMIN_ZONE_TYPES,
    CLIMATE_ANCHOR_TYPE,
    MANUAL_EXCLUSION_GRID,
    AnchorSource,
    ClimateAnchorPoint,
)
from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.locations import static_map_anchors
from app.application.worldData.generators.climate.math import dist_sq
from app.application.worldData.generators.coordinates import (
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def collect_manual_anchors(
    locations: list[NamedLocation],
    cell_m: int,
) -> list[ClimateAnchorPoint]:
    points: list[ClimateAnchorPoint] = []
    for loc in static_map_anchors(locations):
        if loc.system_location_type != CLIMATE_ANCHOR_TYPE:
            continue
        if not loc.system_climate_zone:
            continue
        points.append(ClimateAnchorPoint(
            gx=meters_to_grid_x(loc.map_x, cell_m),
            gy=meters_to_grid_y(loc.map_y, cell_m),
            system_climate_zone=loc.system_climate_zone,
            location_uid=loc.location_uid,
            source=AnchorSource.MANUAL,
        ))
    return points


def collect_admin_anchors(
    locations: list[NamedLocation],
    cell_m: int,
) -> list[ClimateAnchorPoint]:
    points: list[ClimateAnchorPoint] = []
    for loc in static_map_anchors(locations):
        if loc.system_location_type not in ADMIN_ZONE_TYPES:
            continue
        climate = loc.system_climate_zone
        if not climate:
            continue
        points.append(ClimateAnchorPoint(
            gx=meters_to_grid_x(loc.map_x, cell_m),
            gy=meters_to_grid_y(loc.map_y, cell_m),
            system_climate_zone=climate,
            location_uid=loc.location_uid,
            source=AnchorSource.ADMIN,
        ))
    return points


def build_coarse_field(
    world: World,
    locations: list[NamedLocation],
    cell_m: int,
) -> ClimateAnchorField:
    """Pass 1 elevation: manual climate anchors + admin zones (no auto)."""
    manual = collect_manual_anchors(locations, cell_m)
    if manual:
        return ClimateAnchorField(tuple(manual))
    admin = collect_admin_anchors(locations, cell_m)
    return ClimateAnchorField(tuple(admin))


def build_merged_field(
    manual: list[ClimateAnchorPoint],
    auto: list[ClimateAnchorPoint],
    locations: list[NamedLocation],
    cell_m: int,
    *,
    world: World,
    include_admin_fallback: bool = True,
) -> ClimateAnchorField:
    """
    Pass 2+ climate: manual first, then auto outside manual exclusion.
    Admin fallback only when no local modifiers and include_admin_fallback (legacy v1).
    """
    merged: list[ClimateAnchorPoint] = list(manual)
    exclusion_sq = MANUAL_EXCLUSION_GRID ** 2

    for candidate in auto:
        if any(dist_sq(candidate.gx, candidate.gy, m.gx, m.gy) <= exclusion_sq for m in manual):
            continue
        merged.append(candidate)

    if merged:
        return ClimateAnchorField(tuple(merged))

    if not include_admin_fallback:
        admin = collect_admin_anchors(locations, cell_m)
        if admin:
            warn_once(
                world.world_uid,
                "admin_skipped_active_pole",
                "climate anchor | world=%s admin zones skipped (active pole tier); count=%d",
                len(admin),
            )
        return ClimateAnchorField(())

    admin = collect_admin_anchors(locations, cell_m)
    return ClimateAnchorField(tuple(admin))
