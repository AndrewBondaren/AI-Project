"""Resolve declare river intents (modes 1/2) at generate — A3 hybrid, B2 classify."""

from __future__ import annotations

from app.application.worldData.generators.coordinates.convert import (
    cell_size_m,
)
from app.application.worldData.generators.terrain.hydrology.classifyRiverSegments import (
    classify_autoresolve_polyline,
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


def _waypoint_meter(wp: HydrologyWaypoint) -> tuple[int, int]:
    return int(wp.x), int(wp.y)


def _location_anchor_meter(
    location_uid: str,
    loc_map: dict[str, NamedLocation],
) -> tuple[int, int] | None:
    loc = loc_map.get(location_uid)
    if loc is None or loc.map_x is None or loc.map_y is None:
        return None
    return int(loc.map_x), int(loc.map_y)


def _resolve_mouth_meter(
    mouth: HydrologyMouth,
    loc_map: dict[str, NamedLocation],
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> tuple[int, int] | None:
    if mouth.location_uid:
        anchor = _location_anchor_meter(mouth.location_uid, loc_map)
        if anchor is None:
            return None
        return _nearest_water_cell(*anchor, occupied) or anchor
    if mouth.x is not None and mouth.y is not None:
        gx, gy = int(mouth.x), int(mouth.y)
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
        source = _waypoint_meter(river.source)
        mouth = _resolve_mouth_meter(river.mouth, loc_map, occupied)
        if mouth is None:
            return []
        return [source, mouth]

    if mode == RiverDeclareMode.VIA_LOCATIONS:
        anchors: list[tuple[int, int]] = []
        for uid in river.route_location_uids:
            pt = _location_anchor_meter(uid, loc_map)
            if pt is not None:
                anchors.append(pt)
        if len(anchors) >= 2 and river.route_location_uids:
            last_uid = river.route_location_uids[-1]
            last = _location_anchor_meter(last_uid, loc_map)
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
    from app.application.worldData.generators.terrain.hydrology.polylineRasterize import (
        bresenham_line,
    )

    anchors = _anchors_for_river(river, loc_map, cell_m, occupied)
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
