"""Procedural river network — planner + classify — D HY-5c."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.terrain.hydrology.classifyRiverSegments import (
    classify_autoresolve_polyline,
)
from app.application.worldData.generators.terrain.hydrology.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.terrain.hydrology.riverNetworkPlanner import (
    plan_river_network,
)
from app.application.worldData.generators.terrain.hydrology.types import HydrologyMasterInput, RiverSegment
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def autoresolve_river_segments(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> list[RiverSegment]:
    type_classify = resolve_river_type_classify(world)
    polylines = plan_river_network(world, heightmap, occupied, type_classify)
    segments: list[RiverSegment] = []
    for index, polyline in enumerate(polylines):
        source = polyline[0]
        edge_uid = f"ar-river-{master.world_uid}-{source[0]}-{source[1]}-{index}"
        segments.append(
            classify_autoresolve_polyline(
                polyline,
                heightmap,
                type_classify,
                edge_uid=edge_uid,
            ),
        )
    return segments
