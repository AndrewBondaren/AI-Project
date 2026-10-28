"""Positive surface composition contracts; checked statically by Pyright."""

from collections.abc import Mapping, Sequence
from typing import assert_type

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanWaitControl
from app.application.worldData.generators.climate.locations import static_map_anchors
from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations, world_bounds_from_world
from app.application.worldData.planning.composition.surfacePlanningEntry import (
    SurfacePlanningEntry,
    surface_world_topology,
)
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningView
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.climate.planning.climatePoints import ClimateKey, PoleClimateSample
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def valid_surface_composition(entry: SurfacePlanningEntry, view: SurfacePlanningView,
    wait: PlanWaitControl, world: World) -> tuple[SurfacePlanBundle, SurfaceWorkingMaps] | None:
    return entry.prepare_captured(view, world=world, wait=wait, resolve_ctx=ResolveContext())


def valid_locations_sequence(world: World, locations: Sequence[NamedLocation],
                             frozen: tuple[NamedLocation, ...]) -> None:
    for rows in (locations, frozen):
        assert_type(static_map_anchors(rows), list[NamedLocation])
        grid_bbox_from_locations(world, rows)
        world_bounds_from_world(world, rows)
        surface_world_topology(world, rows)
    world_bounds_from_world(world, None)


def valid_surface_working(working: SurfaceWorkingMaps, gx: GridX, gy: GridY,
                          zone: ClimateKey) -> PoleClimateSample:
    assert_type(working.hydrology.fine_z_for_tile(gx, gy), Mapping[tuple[int, int], int])
    assert_type(working.climate.profile_for_key(zone), ClimateZoneProfile)
    assert_type(working.terrain.relief_z, Mapping[tuple[int, int], int])
    return working.climate.sample_pole(gx, gy)
