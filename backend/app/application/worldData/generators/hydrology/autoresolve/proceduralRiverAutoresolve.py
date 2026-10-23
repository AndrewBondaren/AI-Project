"""Procedural river network — planner + classify — D HY-5c."""

from __future__ import annotations

from typing import Any
from app.dataModel.topology.worldTopology import WorldTopology

from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import (
    classify_autoresolve_polyline,
)
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import (
    plan_river_network, plan_prepared_river_network,
)
from app.application.worldData.generators.hydrology.types import HydrologyMasterInput, RiverSegment
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy, RiverTypeClassify
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.topology.worldTopology import Coord
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import (
    RiverRouteRequest, request_from_prepared_segments,
)


def autoresolve_river_segments(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
    occupied: dict[tuple[int, int], MapCellHydrology],
    *, topology: WorldTopology,
) -> list[RiverSegment]:
    type_classify = resolve_river_type_classify(world)
    polylines = plan_river_network(world, heightmap, occupied, type_classify, topology=topology)
    return _segments_from_paths(master.world_uid, heightmap, type_classify, polylines)


def _segments_from_paths(world_uid: str, heightmap: SurfaceHeightmap, type_classify: RiverTypeClassify,
                         polylines: list[list[Coord]]) -> list[RiverSegment]:
    segments: list[RiverSegment] = []
    for index, polyline in enumerate(polylines):
        source = polyline[0]
        edge_uid = f"ar-river-{world_uid}-{source[0]}-{source[1]}-{index}"
        segments.append(
            classify_autoresolve_polyline(
                polyline,
                heightmap,
                type_classify,
                edge_uid=edge_uid,
            ),
        )
    return segments


def prepare_procedural_river_requests(world_uid: EntityUid, seed: int, policy: HydrologyRiversPolicy,
    surface: SurfaceHeightmap, occupied: dict[Coord, MapCellHydrology], topology: WorldTopology, span: int,
) -> tuple[RiverRouteRequest, ...]:
    paths = plan_prepared_river_network(world_uid, seed, policy, surface, occupied,
                                      policy.type_classify, topology=topology)
    segments = _segments_from_paths(world_uid, surface, policy.type_classify, paths)
    return tuple(request_from_prepared_segments(span, (segment,), occupied, surface.surface_z,
        space=CoordinateSpace.WORLD_SURFACE_GRID) for segment in segments)
