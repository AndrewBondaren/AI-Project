"""Shared fixtures for hydrology tests — single source for world/heightmap/wire builders.

Plan: .cursor/plans/hydrology-test-fixtures.md
"""

from __future__ import annotations

from types import SimpleNamespace

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.types import (
    HydrologyMasterInput,
    HydrologyScope,
    LoadedConnectionGraph,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.terrain.worldMapSettings import DEFAULT_GRID_BBOX_PADDING
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.db.models.namedLocation import NamedLocation


def hydro_topology(heightmap: SurfaceHeightmap, mode: WorldTopologyMode = WorldTopologyMode.PLANAR) -> WorldTopology:
    """Explicit topology for tests of the legacy planar water-side contract."""
    bbox = heightmap.bbox
    return WorldTopology(mode=mode, bounds=WorldBounds(
        x_min=bbox.x_min, x_max=bbox.x_max, y_min=bbox.y_min, y_max=bbox.y_max,
    ))


def hydro_world(**kwargs) -> SimpleNamespace:
    defaults = {
        "world_uid": "test-world",
        "hydrology": {"enabled": True},
        "fine_cells_per_map_cell": 3000,
        "terrain_registry": None,
        "terrain_masks": None,
        "terrain_scalars": None,
        "closed_planet_grid": False,
        "magma_band_thickness": None,
        "z_min": 0,
        "z_max": 20,
        "map_subsurface_depth": 0,
        "grid_bbox_padding": DEFAULT_GRID_BBOX_PADDING,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def world_hydrology_dump() -> dict:
    return WorldHydrology().model_dump(mode="json")


def flat_heightmap(
    gx_lo: int,
    gx_hi: int,
    gy_lo: int,
    gy_hi: int,
    z: int = 5,
    *,
    world_uid: str = "test-world",
) -> SurfaceHeightmap:
    return SurfaceHeightmap(
        world_uid=world_uid,
        bbox=GridBBox(gx_lo, gx_hi, gy_lo, gy_hi),
        surface_z={
            (gx, gy): z
            for gx in range(gx_lo, gx_hi + 1)
            for gy in range(gy_lo, gy_hi + 1)
        },
    )


def heightmap_from_z(
    surface_z: dict[tuple[int, int], int],
    *,
    world_uid: str = "test-world",
) -> SurfaceHeightmap:
    xs = [gx for gx, _ in surface_z]
    ys = [gy for _, gy in surface_z]
    return SurfaceHeightmap(
        world_uid=world_uid,
        bbox=GridBBox(min(xs), max(xs), min(ys), max(ys)),
        surface_z=dict(surface_z),
    )


def carve_then_fill(world, heightmap, *, scopes=None, locations=None):
    """Production water path: shared placement → relief carve → read-only fill."""
    from app.application.worldData.generators.hydrology.placement import run_water_placement_pass
    from app.application.worldData.generators.hydrology.hydrologyGeneratorService import HydrologyGeneratorService
    from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z
    locations = locations or []
    water = run_water_placement_pass(world, locations, heightmap)
    if water is not None:
        apply_basin_z(heightmap, water.basin_specs, water.topology, reserved=frozenset())
    before_fill = dict(heightmap.surface_z)
    result = HydrologyGeneratorService().apply(
        world, locations, heightmap, scopes=scopes,
        basin_specs=water.basin_specs if water else (), topology=water.topology if water else None,
    )
    return result, before_fill


def depression_heightmap() -> SurfaceHeightmap:
    surface_z: dict[tuple[int, int], int] = {}
    for gx in range(0, 11):
        for gy in range(0, 11):
            ring = max(abs(gx - 5), abs(gy - 5))
            if ring == 0:
                surface_z[(gx, gy)] = 7950
            elif ring == 1:
                surface_z[(gx, gy)] = 8000
            elif ring <= 3:
                surface_z[(gx, gy)] = 8010
            else:
                surface_z[(gx, gy)] = 8050
    return heightmap_from_z(surface_z)


def hydro_master(**changes) -> HydrologyMasterInput:
    changes.setdefault("world_uid", "test-world")
    changes.setdefault("hydrology_enabled", True)
    changes.setdefault("scopes", frozenset(HydrologyScope))
    changes.setdefault("connection_graph", LoadedConnectionGraph(nodes=[], edges=[]))
    return HydrologyMasterInput(**changes)


def waypoint(x: int, y: int, z: int = 0) -> dict:
    return {"x": x, "y": y, "z": z}


def named_location(location_uid: str, x: int, y: int) -> NamedLocation:
    return NamedLocation(
        location_uid=location_uid,
        world_uid="test-world",
        display_name=location_uid,
        system_location_type="geographic",
        created_at="2026-01-01T00:00:00",
        map_x=x,
        map_y=y,
    )


SQUARE = [((3, 3), (7, 3)), ((7, 3), (7, 7)), ((7, 7), (3, 7)), ((3, 7), (3, 3))]

COASTLINE_PATH_WIRE = [waypoint(6000, 6000), waypoint(24000, 6000)]


# --- world.hydrology presets (fresh dict per call) ---


def seas_hydrology(*, bands: tuple[int, int] = (1, 2), autoresolve: bool = True) -> dict:
    seas: dict = {"bands": {"min": bands[0], "max": bands[1]}}
    if autoresolve:
        seas["autoresolve_coastal_sea"] = True
        seas["autoresolve_open_ocean"] = True
    return {"enabled": True, "default_seas": seas}


def lakes_hydrology() -> dict:
    return {
        "enabled": True,
        "default_lakes": {"enabled": True, "autoresolve": True, "bands": {"min": 1, "max": 4}},
    }


def rivers_hydrology() -> dict:
    return {"enabled": True, "default_rivers": {"enabled": True, "autoresolve": True}}


def seas_lakes_hydrology() -> dict:
    return {**seas_hydrology(), **lakes_hydrology()}


def coastline_world(
    *,
    location_uid: str | None = "loc-sea",
    bands: tuple[int, int] = (1, 2),
    autoresolve: bool = True,
    path: list | None = None,
    **kwargs,
) -> SimpleNamespace:
    hydrology = {
        **seas_hydrology(bands=bands, autoresolve=autoresolve),
        "declared_coastlines": [{
            "location_uid": location_uid,
            "kind": "sea",
            "path": path or COASTLINE_PATH_WIRE,
        }],
    }
    override = kwargs.pop("hydrology", None)
    if override:
        hydrology = {**hydrology, **override}
    return hydro_world(hydrology=hydrology, **kwargs)


# --- declared wire dicts (fine-cell coords) ---


def lake_wire() -> dict:
    return {
        "location_uid": "loc-lake",
        "shoreline": [
            waypoint(3000, 3000),
            waypoint(7000, 3000),
            waypoint(7000, 7000),
            waypoint(3000, 7000),
        ],
    }


def river_segments_wire(**changes) -> dict:
    wire = {
        "location_uid": "loc-river",
        "system_role": "stem",
        "declare_mode": "segments",
        "segments": [{
            "from": waypoint(1000, 9000),
            "to": waypoint(5000, 9000),
            "connection_type": "river_lowland",
            "width_cells": 1,
        }],
    }
    wire.update(changes)
    return wire


def river_endpoints_wire(**changes) -> dict:
    wire = {
        "location_uid": "loc-river-ep",
        "system_role": "stem",
        "declare_mode": "endpoints",
        "source": waypoint(2000, 2000),
        "mouth": waypoint(6000, 2000),
    }
    wire.update(changes)
    return wire
