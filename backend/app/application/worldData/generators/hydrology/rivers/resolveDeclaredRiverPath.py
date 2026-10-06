"""Resolve declare river intents (modes 1/2) at generate — A3 hybrid, B2 classify."""

from __future__ import annotations

from collections.abc import Callable

from app.application.worldData.generators.coordinates.convert import (
    fine_to_grid_xy,
    map_cell_fine_span,
)
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import (
    classify_autoresolve_polyline,
)
from app.application.worldData.generators.hydrology.types import (
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


Cell = tuple[int, int]
FineToSpace = Callable[[Cell], Cell]


def _fine_to_space(world: object, space: CoordinateSpace) -> FineToSpace:
    if space == CoordinateSpace.WORLD_FINE_GRID:
        return lambda pt: pt
    if space == CoordinateSpace.WORLD_SURFACE_GRID:
        map_cell = map_cell_fine_span(world)  # type: ignore[arg-type]
        return lambda pt: fine_to_grid_xy(pt[0], pt[1], map_cell)
    raise ValueError(f"unsupported river intent space: {space}")


def _waypoint_fine(wp: HydrologyWaypoint) -> Cell:
    return int(wp.x), int(wp.y)


def _location_anchor_fine(
    location_uid: str,
    loc_map: dict[str, NamedLocation],
) -> tuple[int, int] | None:
    loc = loc_map.get(location_uid)
    if loc is None or loc.map_x is None or loc.map_y is None:
        return None
    return int(loc.map_x), int(loc.map_y)


def _resolve_mouth(
    mouth: HydrologyMouth,
    loc_map: dict[str, NamedLocation],
    occupied: dict[tuple[int, int], MapCellHydrology],
    to_space: FineToSpace,
) -> Cell | None:
    if mouth.location_uid:
        anchor = _location_anchor_fine(mouth.location_uid, loc_map)
        if anchor is None:
            return None
        cell = to_space(anchor)
    elif mouth.x is not None and mouth.y is not None:
        cell = to_space((int(mouth.x), int(mouth.y)))
    else:
        return None
    return _nearest_water_cell(*cell, occupied) or cell


def _anchors_for_river(
    river: DeclaredRiver,
    loc_map: dict[str, NamedLocation],
    to_space: FineToSpace,
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> list[Cell]:
    mode = river.declare_mode
    if mode == RiverDeclareMode.ENDPOINTS:
        if river.source is None or river.mouth is None:
            return []
        source = to_space(_waypoint_fine(river.source))
        mouth = _resolve_mouth(river.mouth, loc_map, occupied, to_space)
        if mouth is None:
            return []
        return [source, mouth]

    if mode == RiverDeclareMode.VIA_LOCATIONS:
        anchors: list[tuple[int, int]] = []
        for uid in river.route_location_uids:
            pt = _location_anchor_fine(uid, loc_map)
            if pt is not None:
                anchors.append(to_space(pt))
        if len(anchors) >= 2 and river.route_location_uids:
            last_uid = river.route_location_uids[-1]
            last = _location_anchor_fine(last_uid, loc_map)
            if last is not None:
                water = _nearest_water_cell(*to_space(last), occupied)
                if water is not None:
                    anchors[-1] = water
        return anchors

    return []


def _polyline_for_river(
    river: DeclaredRiver,
    heightmap: SurfaceHeightmap,
    loc_map: dict[str, NamedLocation],
    to_space: FineToSpace,
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> list[Cell]:
    from app.application.worldData.generators.hydrology.geom.polylineRasterize import (
        bresenham_line,
    )

    anchors = _anchors_for_river(river, loc_map, to_space, occupied)
    if len(anchors) < 2:
        return []

    polyline: list[tuple[int, int]] = []
    for start, end in zip(anchors, anchors[1:]):
        leg = bresenham_line(start[0], start[1], end[0], end[1])
        if not leg:
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
    *,
    space: CoordinateSpace,
) -> list[RiverSegment]:
    """Modes endpoints / via_locations → classified segments (B2) in ``space`` of ``heightmap``."""
    to_space = _fine_to_space(world, space)
    loc_map = {loc.location_uid: loc for loc in locations}
    segments: list[RiverSegment] = []

    for river in rivers:
        polyline = _polyline_for_river(river, heightmap, loc_map, to_space, occupied)
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
