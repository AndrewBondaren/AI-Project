"""Sparse pre-river sampling and resolved water projection, before fine planning."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.coordinates.convert import (
    fine_to_grid_xy, grid_tile_origin_x, grid_tile_origin_y, map_cell_fine_span,
)
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.geom.polylineRasterize import bresenham_line
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import LoadedDeclaredHydrology
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import classify_river_type
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest
from app.application.worldData.generators.hydrology.types import RiverTypeClassify
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.topologyGeometry import unrolled_images
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _authored_routes(loaded: LoadedDeclaredHydrology, locations: Sequence[NamedLocation]) -> list[list[Coord]]:
    anchors = {loc.location_uid: (int(loc.map_x), int(loc.map_y)) for loc in locations
               if loc.map_x is not None and loc.map_y is not None}
    routes = [list(edge.segment) for edge in loaded.river_edges]
    for river in loaded.river_intents:
        if river.declare_mode is RiverDeclareMode.ENDPOINTS:
            mouth = river.mouth
            target = anchors.get(mouth.location_uid) if mouth.location_uid else (mouth.x, mouth.y)
            points = [(river.source.x, river.source.y), target]
        elif river.declare_mode is RiverDeclareMode.VIA_LOCATIONS:
            points = [anchors.get(uid) for uid in river.route_location_uids]
        else:
            continue
        routes.append([point for point in points if point is not None])
    return routes


def _window(topology: WorldTopology, center: Coord, radius: int) -> Iterable[Coord]:
    """Rasterize a local search envelope; seam/fold IO belongs to topology."""
    x0, x1 = center[0] - radius, center[0] + radius
    y0, y1 = center[1] - radius, center[1] + radius
    if topology.mode is WorldTopologyMode.PLANAR:
        bounds = topology.bounds
        x0, x1 = max(x0, bounds.x_min), min(x1, bounds.x_max)
        y0, y1 = max(y0, bounds.y_min), min(y1, bounds.y_max)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if (cell := topology.canonicalize(x, y)) is not None:
                yield cell


def _planning_cells(routes: Sequence[Sequence[Coord]], topology: WorldTopology,
                    policy: HydrologyRiversPolicy, has_water: bool) -> set[Coord]:
    cells = set()
    for points in routes:
        for start, end in zip(points, points[1:]):
            image = unrolled_images(topology, end, anchor=start)[0].coord
            cells.update(canonical for cell in bresenham_line(*start, *image)
                         if (canonical := topology.canonicalize(*cell)) is not None)
        if points and has_water:
            cells.update(_window(topology, points[0], policy.max_path_cells - 1))
            cells.update(_window(topology, points[-1], policy.mouth_search_radius_fine))
    return cells


def _sample_coarse_to_fine(base: Mapping[Coord, int], cells: Iterable[Coord], span: int) -> dict[Coord, int]:
    samples = {cell: fine_to_grid_xy(*cell, span) for cell in cells}
    return {cell: base[grid] for cell, grid in samples.items() if grid in base}


def _project_hydro(index: Mapping[Coord, MapCellHydrology], cells: Iterable[Coord], span: int,
                   refined_uids: set[str]) -> dict[Coord, MapCellHydrology]:
    projected = {}
    for cell in cells:
        entry = index.get(fine_to_grid_xy(*cell, span))
        if entry is not None and not (entry.role is Role.RIVER_BED and entry.water_body_uid in refined_uids):
            projected[cell] = entry
    return projected


@dataclass(frozen=True)
class FineRiverSampling:
    heightmap: SurfaceHeightmap
    occupied: dict[Coord, MapCellHydrology]
    base: Mapping[Coord, int]
    source_hydro: Mapping[Coord, MapCellHydrology]
    refined_uids: set[str]
    space: CoordinateSpace
    span: int

    def output_heightmap(self, cells: Iterable[Coord]) -> SurfaceHeightmap:
        """Search-only samples must not become unrelated terrain overrides."""
        if self.space is CoordinateSpace.WORLD_FINE_GRID:
            return self.heightmap
        retained = set(cells)
        return replace(self.heightmap, surface_z={cell: z for cell, z in self.heightmap.surface_z.items()
                                                 if cell in retained})

    def sample_requests(self, requests: Sequence[RiverRouteRequest], classify: RiverTypeClassify) -> list[RiverRouteRequest]:
        """Mouth snap can introduce new cells; sample them before final classification."""
        cells = {cell for request in requests for segment in request.segments for cell in segment.polyline_cells}
        if self.space is CoordinateSpace.WORLD_SURFACE_GRID:
            self.heightmap.surface_z.update(_sample_coarse_to_fine(self.base, cells, self.span))
            self.occupied.update(_project_hydro(self.source_hydro, cells, self.span, self.refined_uids))
        result = []
        for request in requests:
            segments = tuple(segment if segment.declared else replace(segment, connection_type=
                classify_river_type(segment.polyline_cells, self.heightmap, classify).value)
                for segment in request.segments)
            kind = classify_river_type(segments[0].polyline_cells, self.heightmap, classify) if (
                segments and not segments[0].declared) else request.object_type
            result.append(replace(request, segments=segments, object_type=kind))
        return result


def sample_fine_river_input(world: World, loaded: LoadedDeclaredHydrology, locations: Sequence[NamedLocation],
                            base: Mapping[Coord, int], topology: WorldTopology, space: CoordinateSpace,
                            coarse_hydro: Mapping[Coord, MapCellHydrology], fine_hydro: Mapping[Coord, MapCellHydrology],
                            policy: HydrologyRiversPolicy) -> FineRiverSampling:
    refined_uids = {edge.location_uid for edge in loaded.river_edges if edge.location_uid}
    refined_uids.update(river.location_uid for river in loaded.river_intents)
    span = map_cell_fine_span(world) if space is CoordinateSpace.WORLD_SURFACE_GRID else 1
    source_hydro = coarse_hydro if space is CoordinateSpace.WORLD_SURFACE_GRID else fine_hydro
    if space is CoordinateSpace.WORLD_SURFACE_GRID:
        wet = any(is_river_mouth(cell, base, source_hydro) for cell in source_hydro)
        cells = _planning_cells(_authored_routes(loaded, locations), topology, policy, wet)
        # Keep one known wet point per coarse cell for global presence diagnostics.
        # Reachability still requires every intervening sampled land cell.
        cells.update(canonical for cell in source_hydro if is_river_mouth(cell, base, source_hydro)
                     if (canonical := topology.canonicalize(
                         grid_tile_origin_x(cell[0], span), grid_tile_origin_y(cell[1], span))) is not None)
        surface_z = _sample_coarse_to_fine(base, cells, span)
    else:
        surface_z = dict(base)
    occupied = _project_hydro(source_hydro, surface_z, span, refined_uids)
    bounds = topology.bounds
    hm = SurfaceHeightmap(world.world_uid, GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max), surface_z)
    return FineRiverSampling(hm, occupied, base, source_hydro, refined_uids, space, span)
