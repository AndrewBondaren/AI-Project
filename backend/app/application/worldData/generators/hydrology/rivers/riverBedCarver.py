"""River channel carve on declare polylines — D HY-4, U24/U28."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import (
    segments_from_declared,
)
from app.application.worldData.generators.hydrology.load.hydrologyAutoresolvePolicy import (
    rivers_autoresolve_policy,
)
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.hydrology.types import (
    HydrologyMasterInput,
    RiverSegment,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def _channel_depth_step(connection_type: str, type_classify) -> int:
    base = 1
    if HydrologyConnectionType.from_wire(connection_type) == HydrologyConnectionType.MOUNTAIN_RIVER:
        return max(1, int(round(base * type_classify.mountain_bed_steepness_factor)))
    return base


def carve_river_segment(
    heightmap: SurfaceHeightmap,
    segment: RiverSegment,
    *,
    depth_step: int,
) -> dict[tuple[int, int], MapCellHydrology]:
    by_cell: dict[tuple[int, int], MapCellHydrology] = {}
    for cell in segment.polyline_cells:
        if cell not in heightmap.surface_z:
            continue
        z = heightmap.surface_z[cell]
        heightmap.surface_z[cell] = max(0, z - depth_step)
        by_cell[cell] = MapCellHydrology(
            role=HydrologyCellRole.RIVER_BED,
            connection_edge_uid=segment.edge_uid,
        )
    return by_cell


def generate_rivers(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
    occupied: dict[tuple[int, int], MapCellHydrology] | None = None,
    locations: list[Any] | None = None,
) -> tuple[dict[tuple[int, int], MapCellHydrology], list[RiverSegment], GridBBox | None]:
    type_classify = resolve_river_type_classify(world)
    river_segments = segments_from_declared(master.declared_river_edges)
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    xs: list[int] = []
    ys: list[int] = []
    occupied_cells = dict(occupied or {})

    if master.declared_river_intents and locations is not None:
        from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import (
            resolve_declared_river_intents,
        )

        for segment in resolve_declared_river_intents(
            world,
            heightmap,
            master.declared_river_intents,
            locations,
            occupied_cells,
            type_classify,
        ):
            river_segments.append(segment)

    for segment in river_segments:
        depth = _channel_depth_step(segment.connection_type, type_classify)
        carved = carve_river_segment(heightmap, segment, depth_step=depth)
        merged.update(carved)
        for cell in carved:
            xs.append(cell[0])
            ys.append(cell[1])

    rivers_policy = rivers_autoresolve_policy(world)
    if rivers_policy.rivers_enabled and rivers_policy.autoresolve:
        from app.application.worldData.generators.hydrology.autoresolve.proceduralRiverAutoresolve import (
            autoresolve_river_segments,
        )

        claim = {**occupied_cells, **merged}
        for segment in autoresolve_river_segments(world, heightmap, master, claim):
            if any(cell in merged for cell in segment.polyline_cells):
                continue
            depth = _channel_depth_step(segment.connection_type, type_classify)
            carved = carve_river_segment(heightmap, segment, depth_step=depth)
            merged.update(carved)
            river_segments.append(segment)
            for cell in carved:
                xs.append(cell[0])
                ys.append(cell[1])

    dirty = None
    if xs and ys:
        dirty = GridBBox(min(xs), max(xs), min(ys), max(ys))
    return merged, river_segments, dirty
