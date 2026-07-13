"""Location territory volumes for pack L2 read/write — DEBT-6 / MERGE-3."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_side_m,
    settlement_meter_rect,
)
from app.application.worldData.generators.terrain.worldMapSettings import n_base, world_z_min
from app.dataModel.locations.locationFootprintPolicy import named_location_uses_settlement_meter_footprint
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.territoryVolumePolicy import TerritoryVolumePolicy
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _inclusive_xy_bounds(x0: int, y0: int, x1_exclusive: int, y1_exclusive: int) -> tuple[int, int, int, int]:
    return x0, y0, max(x0, x1_exclusive - 1), max(y0, y1_exclusive - 1)


def _settlement_territory_volume(world: World, location: NamedLocation) -> TerritoryVolume | None:
    if location.map_x is None or location.map_y is None:
        return None
    policy = TerritoryVolumePolicy.canonical_defaults()
    rect = settlement_meter_rect(world, location)
    x0, y0, x1, y1 = _inclusive_xy_bounds(int(rect.x0), int(rect.y0), int(rect.x1), int(rect.y1))
    ground_z = int(rect.z)
    depth = n_base(world)
    return TerritoryVolume(
        x0=x0,
        y0=y0,
        z0=max(world_z_min(world), ground_z - depth),
        x1=x1,
        y1=y1,
        z1=ground_z + policy.settlement_z_above,
    )


def _pin_territory_volume(
    world: World,
    location: NamedLocation,
    *,
    policy: TerritoryVolumePolicy,
) -> TerritoryVolume | None:
    if location.map_x is None or location.map_y is None:
        return None
    half = TerritoryVolumePolicy.pin_half_extent_xy()
    ground_z = location.map_z if location.map_z is not None else policy.pin_map_z_fallback
    depth = n_base(world)
    return TerritoryVolume(
        x0=location.map_x - half,
        y0=location.map_y - half,
        z0=max(world_z_min(world), ground_z - depth),
        x1=location.map_x + half,
        y1=location.map_y + half,
        z1=ground_z + policy.pin_z_above,
    )


def territory_volume_for_location(world: World, location: NamedLocation) -> TerritoryVolume | None:
    """Settlement footprint from assembler; pin locations use POJO policy box."""
    if named_location_uses_settlement_meter_footprint(location):
        return _settlement_territory_volume(world, location)
    return _pin_territory_volume(world, location, policy=TerritoryVolumePolicy.canonical_defaults())


def territory_volumes_by_location(
    world: World,
    locations: list[NamedLocation],
) -> list[tuple[str, TerritoryVolume]]:
    out: list[tuple[str, TerritoryVolume]] = []
    for location in locations:
        volume = territory_volume_for_location(world, location)
        if volume is not None:
            out.append((location.location_uid, volume))
    return out


def settlement_footprint_side_m(world: World, location: NamedLocation) -> int | None:
    """Expose footprint side for tests/debug without duplicating POJO math."""
    if not named_location_uses_settlement_meter_footprint(location):
        return None
    size = location.system_city_size
    return footprint_side_m(world, size)
