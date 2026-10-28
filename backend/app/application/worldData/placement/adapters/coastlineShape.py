"""Pre-carve coastline geometry; no fill, carve, or inter-object winner selection."""

from collections import deque
import heapq
from math import floor

from pydantic import ValidationError

from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.shore.waterSideFootprint import CoastlineWaterSide
from app.application.worldData.placement.adapters.waterTypes import WaterGeometryError, WaterGeometryView
from app.dataModel.identity.uid import EntityUid
from app.application.worldData.placement.adapters.waterShape import shape_cells
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.spatial.regionShape import PolygonShape
from app.dataModel.topology import topologyGeometry as geometry
from app.dataModel.topology.worldTopology import Coord, WorldTopology


def cell_neighbors(topology: WorldTopology, cell: Coord):
    return iter(geometry.canonical_neighbors4(topology, cell))


def ring_barrier(context: WaterGeometryView,
                 segments: list[tuple[Coord, Coord]]) -> set[Coord]:
    barrier: set[Coord] = set()
    for cell in rasterize_segments(segments):
        canonical = context.topology.canonicalize(*cell)
        if canonical is None:
            raise WaterGeometryError("ring extends outside planar world")
        barrier.add(canonical)
    return barrier


def ring_sides(polygon: PolygonShape, source_uid: str, context: WaterGeometryView,
               barrier: set[Coord], *, seed_root: EntityUid) -> tuple[set[Coord], set[Coord]]:
    inside = set(shape_cells(polygon, source_uid, context, seed_root=seed_root)[0]) - barrier
    outside = set(context.surface_z) - barrier - inside
    # Every complementary component must have one consistent side. A
    # nonseparating ring must never acquire a bbox-derived interior on a torus.
    remaining = inside | outside
    while remaining:
        root = min(remaining)
        expected_inside = root in inside
        remaining.remove(root)
        queue = deque([root])
        while queue:
            cell = queue.popleft()
            if (cell in inside) != expected_inside:
                raise WaterGeometryError("nonseparating or ambiguous topology ring; declare an explicit basin")
            for neighbor in cell_neighbors(context.topology, cell):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
    return inside, outside


def coastline_segments(entry: DeclaredCoastline) -> tuple[tuple[Coord, Coord], ...]:
    """One source of segment assembly for the water claim and terrain constraints."""
    points = [(point.x, point.y) for point in entry.path]
    if points[0] == points[-1]:
        points.pop()
    segments = list(zip(points, points[1:]))
    if entry.closed:
        segments.append((points[-1], points[0]))
    return tuple(segments)


def coastline_cells(entry: DeclaredCoastline, context: WaterGeometryView,
                    policy: HydrologySeasPolicy, *, seed_root: EntityUid) -> tuple[frozenset[Coord], bool]:
    segments = list(coastline_segments(entry))
    points = [a for a, _ in segments]
    if entry.closed:
        try:
            polygon = PolygonShape(vertices=tuple(points))
        except ValidationError as error:
            raise WaterGeometryError(f"invalid coastline ring: {error.errors()[0]['msg']}") from error
        inside, outside = ring_sides(polygon, entry.location_uid, context,
                                     ring_barrier(context, segments), seed_root=seed_root)
        if not inside or not outside:
            raise WaterGeometryError("ring does not separate an interior and exterior; declare an explicit basin")
        return frozenset(inside if entry.water_side == WaterSide.INTERIOR else outside), False
    topology = context.topology
    coast = set(rasterize_segments(segments))
    if any(topology.canonicalize(*cell) is None for cell in coast):
        raise WaterGeometryError("coastline extends outside planar world")
    anchor = points[0]
    centroid = geometry.centroid(topology, sorted(context.surface_z),
                                 (max(context.surface_z[cell], 1) for cell in sorted(context.surface_z)), anchor)
    side = CoastlineWaterSide(coast, segments, centroid, topology=topology)
    bounds = topology.bounds
    cap = max(1, floor(policy.max_area_fraction * bounds.width * bounds.height))

    def eligible(cell: Coord) -> bool:
        if not side.contains(cell, bounded=False):
            return False
        projection = min((geometry.nearest_on_segment(topology, cell, a, b) for a, b in segments),
                         key=lambda result: (result.distance2, result.nearest[1], result.nearest[0]))
        dx = abs(projection.image.coord[0] - projection.nearest[0])
        dy = abs(projection.image.coord[1] - projection.nearest[1])
        # Both wet and dry expansion obey hard extent caps. A dry candidate
        # remains valid: future creation of water is not this pass's support.
        return (dx <= policy.max_extent_x_fraction * bounds.width
                and dy <= policy.max_extent_y_fraction * bounds.height)

    seeds = {topology.canonicalize(*cell) for cell in side.seeds(lambda cell: cell in context.surface_z)}
    frontier = [(0, cell[1], cell[0]) for cell in seeds if cell is not None and eligible(cell)]
    heapq.heapify(frontier)
    visited, cells = set(), set()
    capped = False
    while frontier:
        distance, y, x = heapq.heappop(frontier)
        cell = (x, y)
        if cell in visited:
            continue
        visited.add(cell)
        if not eligible(cell):
            # A reachable water-side frontier met a hard extent boundary.
            capped = True
            continue
        if len(cells) == cap:
            capped = True
            break
        cells.add(cell)
        for neighbor in cell_neighbors(topology, cell):
            if neighbor not in visited and side.contains(neighbor, bounded=False):
                heapq.heappush(frontier, (distance + 1, neighbor[1], neighbor[0]))
    if not cells:
        raise WaterGeometryError("coastline has no reachable water-side candidate cells")
    return frozenset(cells), capped
