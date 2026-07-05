"""Resolve declare river intents (modes 1/2) at generate — A3 hybrid, B2 classify."""

from __future__ import annotations

from app.application.worldData.generators.coordinates.convert import (
    cell_size_m,
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.application.worldData.generators.terrain.hydrology.classifyRiverSegments import (
    classify_autoresolve_polyline,
)
from app.application.worldData.generators.terrain.hydrology.riverNetworkPlanner import (
    plan_path_to_target,
)
from app.application.worldData.generators.terrain.hydrology.types import (
    RiverSegment,
    RiverTypeClassify,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, HydrologyMouth
from app.db.models.mapCell import MapCell
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.db.models.namedLocation import NamedLocation


def _is_water(entry: MapCellHydrology | None) -> bool:
    return entry is not None and entry.role is not None and entry.role.is_open_water_role()


def _nearest_water_cell(
    gx: int,
    gy: int,
    occupied: dict[tuple[int, int], MapCellHydrology],
    *,
    max_radius: int = 24,
) -> tuple[int, int] | None:
    if (gx, gy) in occupied and _is_water(occupied.get((gx, gy))):
        return (gx, gy)
    for radius in range(1, max_radius + 1):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) + abs(dy) != radius:
                    continue
                cell = (gx + dx, gy + dy)
                if _is_water(occupied.get(cell)):
                    return cell
    return None


def _waypoint_to_grid(
    wp: HydrologyWaypoint,
    cell_m: int,
) -> tuple[int, int]:
    return (
        int(meters_to_grid_x(wp.x, cell_m)),
        int(meters_to_grid_y(wp.y, cell_m)),
    )


def _location_anchor_grid(
    location_uid: str,
    loc_map: dict[str, NamedLocation],
    cell_m: int,
) -> tuple[int, int] | None:
    loc = loc_map.get(location_uid)
    if loc is None or loc.map_x is None or loc.map_y is None:
        return None
    return (
        int(meters_to_grid_x(int(loc.map_x), cell_m)),
        int(meters_to_grid_y(int(loc.map_y), cell_m)),
    )


def _resolve_mouth_grid(
    mouth: HydrologyMouth,
    loc_map: dict[str, NamedLocation],
    cell_m: int,
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> tuple[int, int] | None:
    if mouth.location_uid:
        anchor = _location_anchor_grid(mouth.location_uid, loc_map, cell_m)
        if anchor is None:
            return None
        return _nearest_water_cell(*anchor, occupied) or anchor
    if mouth.x is not None and mouth.y is not None:
        gx = int(meters_to_grid_x(int(mouth.x), cell_m))
        gy = int(meters_to_grid_y(int(mouth.y), cell_m))
        return _nearest_water_cell(gx, gy, occupied) or (gx, gy)
    return None


def _anchors_for_river(
    river: DeclaredRiver,
    loc_map: dict[str, NamedLocation],
    cell_m: int,
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> list[tuple[int, int]]:
    mode = river.declare_mode
    if mode == RiverDeclareMode.ENDPOINTS:
        if river.source is None or river.mouth is None:
            return []
        source = _waypoint_to_grid(river.source, cell_m)
        mouth = _resolve_mouth_grid(river.mouth, loc_map, cell_m, occupied)
        if mouth is None:
            return []
        return [source, mouth]

    if mode == RiverDeclareMode.VIA_LOCATIONS:
        anchors: list[tuple[int, int]] = []
        for uid in river.route_location_uids:
            pt = _location_anchor_grid(uid, loc_map, cell_m)
            if pt is not None:
                anchors.append(pt)
        if len(anchors) >= 2 and river.route_location_uids:
            last_uid = river.route_location_uids[-1]
            last = _location_anchor_grid(last_uid, loc_map, cell_m)
            if last is not None:
                water = _nearest_water_cell(*last, occupied)
                if water is not None:
                    anchors[-1] = water
        return anchors

    return []


def _polyline_for_river(
    river: DeclaredRiver,
    heightmap: SurfaceHeightmap,
    loc_map: dict[str, NamedLocation],
    cell_m: int,
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> list[tuple[int, int]]:
    anchors = _anchors_for_river(river, loc_map, cell_m, occupied)
    if len(anchors) < 2:
        return []

    polyline: list[tuple[int, int]] = []
    for start, end in zip(anchors, anchors[1:]):
        leg = plan_path_to_target(heightmap, start, end, occupied)
        if len(leg) < 2:
            continue
        if polyline and polyline[-1] == leg[0]:
            polyline.extend(leg[1:])
        else:
            polyline.extend(leg)
    return polyline


def resolve_declared_river_intents(
    world: object,
    heightmap: SurfaceHeightmap,
    rivers: list[DeclaredRiver],
    locations: list[NamedLocation],
    occupied: dict[tuple[int, int], MapCellHydrology],
    type_classify: RiverTypeClassify,
) -> list[RiverSegment]:
    """Modes endpoints / via_locations → classified segments (B2)."""
    cell_m = cell_size_m(world)  # type: ignore[arg-type]
    loc_map = {loc.location_uid: loc for loc in locations}
    segments: list[RiverSegment] = []

    for river in rivers:
        polyline = _polyline_for_river(river, heightmap, loc_map, cell_m, occupied)
        if len(polyline) < 2:
            continue
        segments.append(
            classify_autoresolve_polyline(
                polyline,
                heightmap,
                type_classify,
                edge_uid=f"dr-{river.location_uid}",
            ),
        )
        segments[-1] = RiverSegment(
            polyline_cells=segments[-1].polyline_cells,
            connection_type=segments[-1].connection_type,
            edge_uid=segments[-1].edge_uid,
            location_uid=river.location_uid,
            declared=False,
        )

    return segments
