"""Declared hydrology carve at world meter resolution (1 m cells)."""

from __future__ import annotations

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.coordinates.worldTile import (
    expand_coarse_hydro_to_tile,
    meter_bbox_for_tile,
)
from app.application.worldData.generators.terrain.hydrology.classifyRiverSegments import (
    segments_from_declared,
)
from app.application.worldData.generators.terrain.hydrology.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.terrain.hydrology.resolveDeclaredRiverPath import (
    resolve_declared_river_intents,
)
from app.application.worldData.generators.terrain.hydrology.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.terrain.hydrology.riverBedCarver import (
    _channel_depth_step,
    carve_river_segment,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def apply_declared_meter_river_carves(
    world: World,
    locations: list[NamedLocation],
    base_surface_z: dict[tuple[int, int], int],
) -> tuple[dict[tuple[int, int], MapCellHydrology], dict[tuple[int, int], int]]:
    """Rasterize declare rivers at meter coords."""
    loaded = load_declared_hydrology(world, locations)
    type_classify = resolve_river_type_classify(world)
    merged_hydro: dict[tuple[int, int], MapCellHydrology] = {}
    surface_z: dict[tuple[int, int], int] = dict(base_surface_z)

    segments = segments_from_declared(loaded.river_edges)
    for segment in segments:
        depth = _channel_depth_step(segment.connection_type, type_classify)
        for cell in segment.polyline_cells:
            z = surface_z.get(cell, 0)
            surface_z[cell] = max(0, z - depth)
            merged_hydro[cell] = MapCellHydrology(
                role=HydrologyCellRole.RIVER_BED,
                connection_edge_uid=segment.edge_uid,
            )

    if surface_z:
        xs = [x for x, _ in surface_z]
        ys = [y for _, y in surface_z]
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(min(xs), max(xs), min(ys), max(ys)),
            surface_z=surface_z,
        )
    else:
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={},
        )

    if loaded.river_intents:
        for segment in resolve_declared_river_intents(
            world,
            hm,
            loaded.river_intents,
            locations,
            merged_hydro,
            type_classify,
        ):
            carved = carve_river_segment(hm, segment, depth_step=1)
            merged_hydro.update(carved)
            surface_z.update(hm.surface_z)

    return merged_hydro, surface_z


def merge_meter_hydro_for_tile(
    tile_gx: int,
    tile_gy: int,
    cell_m: int,
    coarse_hydro: dict[tuple[int, int], MapCellHydrology],
    sparse_meter_hydro: dict[tuple[int, int], MapCellHydrology],
) -> dict[tuple[int, int], MapCellHydrology]:
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    merged.update(expand_coarse_hydro_to_tile(coarse_hydro, tile_gx, tile_gy, cell_m))

    meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
    for (xm, ym), entry in sparse_meter_hydro.items():
        if (
            meter_bbox.x_min <= xm <= meter_bbox.x_max
            and meter_bbox.y_min <= ym <= meter_bbox.y_max
        ):
            merged[(xm, ym)] = entry

    return merged
