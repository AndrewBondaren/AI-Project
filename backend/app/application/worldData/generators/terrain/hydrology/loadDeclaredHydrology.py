"""Wire `world.hydrology.declared_*` → generator runtime types."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.jsonValidation.worldRow import hydrology as read_hydrology
from app.application.worldData.generators.coordinates.convert import (
    cell_size_m,
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.application.worldData.generators.terrain.hydrology.basinKindResolver import (
    resolve_lake_basin_role,
)
from app.application.worldData.generators.terrain.hydrology.lakeSpecs import _group_segments
from app.application.worldData.generators.terrain.hydrology.types import (
    DeclaredRiverEdge,
    LakeSpec,
)
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.enums.riverSystemRole import RiverSystemRole
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass(frozen=True)
class LoadedDeclaredHydrology:
    coastline_segments: list[tuple[tuple[int, int], tuple[int, int]]]
    lake_specs: list[LakeSpec]
    river_edges: list[DeclaredRiverEdge]
    river_intents: list[DeclaredRiver]


def _waypoint_grid(
    wp: HydrologyWaypoint,
    cell_m: int,
) -> tuple[int, int]:
    return (
        int(meters_to_grid_x(wp.x, cell_m)),
        int(meters_to_grid_y(wp.y, cell_m)),
    )


def _path_to_segments(
    points: list[HydrologyWaypoint],
    cell_m: int,
    *,
    closed: bool = False,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if len(points) < 2:
        return []
    grid_pts = [_waypoint_grid(p, cell_m) for p in points]
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for i in range(len(grid_pts) - 1):
        segments.append((grid_pts[i], grid_pts[i + 1]))
    if closed and len(grid_pts) >= 3:
        segments.append((grid_pts[-1], grid_pts[0]))
    return segments


def _segments_from_declared_river(river: DeclaredRiver, cell_m: int) -> list[DeclaredRiverEdge]:
    if river.declare_mode != RiverDeclareMode.SEGMENTS:
        return []
    edges: list[DeclaredRiverEdge] = []
    for index, seg in enumerate(river.segments):
        a = _waypoint_grid(seg.from_wp, cell_m)
        b = _waypoint_grid(seg.to_wp, cell_m)
        edges.append(DeclaredRiverEdge(
            edge_uid=f"dr-{river.location_uid}-{index}",
            segment=(a, b),
            connection_type=seg.connection_type,
            width_cells=int(seg.width_cells),
            location_uid=river.location_uid,
        ))
    return edges


def load_declared_hydrology(
    world: World,
    locations: list[NamedLocation],
) -> LoadedDeclaredHydrology:
    """Read POJO declare from world; segments mode → edges at import (A3 hybrid)."""
    pojo = read_hydrology(world)
    cell_m = cell_size_m(world)
    loc_map = {loc.location_uid: loc for loc in locations}

    coastline_segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for entry in pojo.declared_coastlines:
        coastline_segments.extend(_path_to_segments(list(entry.path), cell_m))

    lake_specs: list[LakeSpec] = []
    for entry in pojo.declared_lakes:
        segments = _path_to_segments(list(entry.shoreline), cell_m, closed=True)
        if not segments:
            continue
        for group in _group_segments(segments):
            open_role = resolve_lake_basin_role(
                entry.location_uid,
                loc_map,
                world_uid=world.world_uid,
                connection_type=HydrologyConnectionType.LAKE_SHORELINE.value,
            )
            lake_specs.append(LakeSpec(
                shoreline_segments=group,
                location_uid=entry.location_uid,
                open_water_role=open_role,
            ))

    river_edges: list[DeclaredRiverEdge] = []
    river_intents: list[DeclaredRiver] = []
    for river in pojo.declared_rivers:
        if river.system_role == RiverSystemRole.SYSTEM:
            continue
        if river.declare_mode == RiverDeclareMode.SEGMENTS:
            river_edges.extend(_segments_from_declared_river(river, cell_m))
        elif river.declare_mode in (RiverDeclareMode.ENDPOINTS, RiverDeclareMode.VIA_LOCATIONS):
            river_intents.append(river)

    return LoadedDeclaredHydrology(
        coastline_segments=coastline_segments,
        lake_specs=lake_specs,
        river_edges=river_edges,
        river_intents=river_intents,
    )
