"""Resolve declare river intents (modes 1/2) at generate — A3 hybrid, B2 classify."""

from __future__ import annotations

from collections.abc import Mapping, Callable, Sequence
from dataclasses import dataclass
from app.application.jsonValidation.worldRow import hydrology

from app.application.worldData.generators.coordinates.convert import (
    fine_to_grid_xy,
    grid_tile_origin_x,
    grid_tile_origin_y,
    map_cell_fine_span,
)
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import (
    classify_autoresolve_polyline,
)
from app.application.worldData.generators.hydrology.types import (
    RiverSegment,
)
from app.dataModel.hydrology.rivers import RiverTypeClassify
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, HydrologyMouth
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.geom.polylineRasterize import bresenham_line
from app.dataModel.topology.topologyGeometry import dist2, unrolled_images
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.db.models.namedLocation import NamedLocation


@dataclass(frozen=True)
class _MouthSearch:
    topology: WorldTopology
    radius_fine: int
    span: int
    river_uids: frozenset[str] = frozenset()
    river_cells: frozenset[Coord] = frozenset()


def _nearest_water_cell(fine_anchor, occupied, *, heightmap, search: _MouthSearch):
    anchor = search.topology.canonicalize(*fine_anchor)
    if anchor is None:
        return None
    ranked = []
    for cell in occupied:
        if not is_river_mouth(cell, heightmap.surface_z, occupied):
            continue
        point = (grid_tile_origin_x(cell[0], search.span), grid_tile_origin_y(cell[1], search.span))
        distance = dist2(search.topology, anchor, point)
        if distance <= search.radius_fine ** 2:
            ranked.append((distance, cell))
    return min(ranked)[1] if ranked else None


Cell = tuple[int, int]
FineToSpace = Callable[[Cell], Cell]


def _waypoint_fine(wp: HydrologyWaypoint) -> Cell:
    return wp.x, wp.y


def _location_anchor_fine(
    location_uid: str,
    loc_map: Mapping[str, Coord],
) -> tuple[int, int] | None:
    return loc_map.get(location_uid)


def _resolve_mouth(
    mouth: HydrologyMouth,
    loc_map: Mapping[str, Coord],
    occupied: dict[tuple[int, int], MapCellHydrology],
    to_space: FineToSpace,
    heightmap: SurfaceHeightmap, search: _MouthSearch,
) -> Cell | None:
    if mouth.location_uid:
        anchor = _location_anchor_fine(mouth.location_uid, loc_map)
        if anchor is None:
            return None
    elif mouth.x is not None and mouth.y is not None:
        anchor = int(mouth.x), int(mouth.y)
    else:
        return None
    cell = to_space(anchor)
    entry = occupied.get(cell)
    if cell in search.river_cells or mouth.location_uid in search.river_uids or (entry is not None and (
            entry.role is Role.RIVER_BED or is_river_mouth(cell, heightmap.surface_z, occupied))):
        return cell
    # The location identifies the anchor, never the water body's identity.
    return _nearest_water_cell(anchor, occupied, heightmap=heightmap, search=search) or cell


def _anchors_for_river(
    river: DeclaredRiver,
    loc_map: Mapping[str, Coord],
    to_space: FineToSpace,
    occupied: dict[tuple[int, int], MapCellHydrology],
    heightmap: SurfaceHeightmap, search: _MouthSearch,
) -> list[Cell]:
    mode = river.declare_mode
    if mode == RiverDeclareMode.ENDPOINTS:
        if river.source is None or river.mouth is None:
            return []
        source = to_space(_waypoint_fine(river.source))
        mouth = _resolve_mouth(river.mouth, loc_map, occupied, to_space, heightmap, search)
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
                water = _resolve_mouth(HydrologyMouth(location_uid=last_uid), loc_map,
                                       occupied, to_space, heightmap, search)
                if water is not None:
                    anchors[-1] = water
        return anchors

    return []


def _polyline_for_river(
    river: DeclaredRiver,
    heightmap: SurfaceHeightmap,
    loc_map: Mapping[str, Coord],
    to_space: FineToSpace,
    occupied: dict[tuple[int, int], MapCellHydrology],
    topology: WorldTopology, search: _MouthSearch,
) -> list[Cell]:
    anchors = _anchors_for_river(river, loc_map, to_space, occupied, heightmap, search)
    if len(anchors) < 2:
        return []

    anchors = [topology.canonicalize(*cell) for cell in anchors]
    if any(cell is None for cell in anchors):
        return []
    polyline: list[tuple[int, int]] = []
    for start, end in zip(anchors, anchors[1:]):
        end_image = unrolled_images(topology, end, anchor=start)[0].coord
        leg = list(dict.fromkeys(canonical for cell in bresenham_line(*start, *end_image)
                   if (canonical := topology.canonicalize(*cell)) is not None))
        if not leg:
            return []
        if polyline and polyline[-1] == leg[0]:
            polyline.extend(leg[1:])
        else:
            polyline.extend(leg)
        if is_river_mouth(polyline[-1], heightmap.surface_z, occupied):
            break
    return polyline


def resolve_prepared_river_intents(
    span: int, radius_fine: int,
    heightmap: SurfaceHeightmap,
    rivers: list[DeclaredRiver],
    locations: Mapping[str, Coord],
    occupied: dict[tuple[int, int], MapCellHydrology],
    type_classify: RiverTypeClassify,
    *,
    space: CoordinateSpace,
    topology: WorldTopology,
    river_uids: frozenset[str] = frozenset(),
    river_cells: frozenset[Coord] = frozenset(),
) -> list[RiverSegment]:
    """Rasterize endpoints/via_locations intents into candidate segments.

    Resolved water must be available before planning. Mouth snapping uses the
    POJO mouth_search_radius_fine in world-fine cells in either working space,
    with topology distance and deterministic ties. An empty rasterized leg
    rejects the candidate instead of silently skipping that leg. Reaching water
    ends rasterization; shared validation decides whether it is an acceptable
    receiver. The caller handles failed requests and runtime fallback; this
    resolver neither materializes beds nor publishes acceptance diagnostics.
    Authored location UID and resolved receiving identity remain separate.
    """
    if not isinstance(topology, WorldTopology):
        raise TypeError("river intents require an explicit WorldTopology")
    if space not in (CoordinateSpace.WORLD_SURFACE_GRID, CoordinateSpace.WORLD_FINE_GRID):
        raise ValueError(f"unsupported river intent space: {space}")
    span = span if space is CoordinateSpace.WORLD_SURFACE_GRID else 1
    to_space = lambda pt: fine_to_grid_xy(*pt, span)
    search = _MouthSearch(fine_topology(topology, span) if span != 1 else topology,
                          radius_fine, span, river_uids, river_cells)
    loc_map = locations
    segments: list[RiverSegment] = []

    for river in rivers:
        polyline = _polyline_for_river(river, heightmap, loc_map, to_space, occupied, topology, search)
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


def resolve_prepared_mouth_cell(span: int, radius_fine: int, mouth: HydrologyMouth, locations: Mapping[str, Coord],
                       occupied: dict[Cell, MapCellHydrology], heightmap: SurfaceHeightmap, *,
                       space: CoordinateSpace, topology: WorldTopology,
                       river_uids: frozenset[str] = frozenset(),
                       river_cells: frozenset[Coord] = frozenset()) -> Cell | None:
    """Resolve an authored anchor once without conflating location and body UID."""
    if not isinstance(topology, WorldTopology):
        raise TypeError("river mouths require an explicit WorldTopology")
    if space not in (CoordinateSpace.WORLD_SURFACE_GRID, CoordinateSpace.WORLD_FINE_GRID):
        raise ValueError(f"unsupported river intent space: {space}")
    span = span if space is CoordinateSpace.WORLD_SURFACE_GRID else 1
    search = _MouthSearch(fine_topology(topology, span) if span != 1 else topology,
                         radius_fine, span, river_uids, river_cells)
    cell = _resolve_mouth(mouth, locations, occupied,
                          lambda pt: fine_to_grid_xy(*pt, span), heightmap, search)
    return topology.canonicalize(*cell) if cell is not None else None


def resolve_declared_river_intents(world: object, heightmap: SurfaceHeightmap,
    rivers: list[DeclaredRiver], locations: list[NamedLocation],
    occupied: dict[Coord, MapCellHydrology], type_classify: RiverTypeClassify, *,
    space: CoordinateSpace, topology: WorldTopology,
    river_uids: frozenset[str] = frozenset(), river_cells: frozenset[Coord] = frozenset(),
) -> list[RiverSegment]:
    return resolve_prepared_river_intents((map_cell_fine_span(world) if space is CoordinateSpace.WORLD_SURFACE_GRID else 1),
        hydrology(world).default_rivers.mouth_search_radius_fine, heightmap, rivers,
        location_anchor_map(locations), occupied, type_classify, space=space,
        topology=topology, river_uids=river_uids, river_cells=river_cells)


def resolve_mouth_cell(world: object, mouth: HydrologyMouth, locations: Sequence[NamedLocation],
    occupied: dict[Coord, MapCellHydrology], heightmap: SurfaceHeightmap, *,
    space: CoordinateSpace, topology: WorldTopology,
    river_uids: frozenset[str] = frozenset(), river_cells: frozenset[Coord] = frozenset(),
) -> Cell | None:
    return resolve_prepared_mouth_cell((map_cell_fine_span(world) if space is CoordinateSpace.WORLD_SURFACE_GRID else 1),
        hydrology(world).default_rivers.mouth_search_radius_fine, mouth,
        location_anchor_map(locations), occupied, heightmap, space=space,
        topology=topology, river_uids=river_uids, river_cells=river_cells)


def location_anchor_map(locations: Sequence[NamedLocation]) -> dict[str, Coord]:
    return {loc.location_uid: (int(loc.map_x), int(loc.map_y)) for loc in locations
            if loc.map_x is not None and loc.map_y is not None}
