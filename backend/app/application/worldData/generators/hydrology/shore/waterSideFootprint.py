"""Declared coastline geometry and reachable footprint, independent of carve/fill."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.topology import topologyGeometry as topology_geometry
from app.dataModel.topology.worldTopology import WorldTopology

Cell = tuple[int, int]
Segment = tuple[Cell, Cell]


def canonical_passable(topology: WorldTopology, passable: Callable[[Cell], bool]) -> Callable[[Cell], bool]:
    """Adapt a canonical membership/eligibility predicate to unrolled traversal."""
    def contains(cell: Cell) -> bool:
        canonical = topology.canonicalize(*cell)
        return canonical is not None and passable(canonical)
    return contains


def compute_land_centroid(heightmap: SurfaceHeightmap, *, topology: WorldTopology,
                          anchor: tuple[float, float] | None = None) -> tuple[float, float]:
    if not heightmap.surface_z:
        return (0.0, 0.0)
    bounds = topology.bounds
    if anchor is None:
        anchor = (bounds.x_min + bounds.x_max) / 2, (bounds.y_min + bounds.y_max) / 2
    return topology_geometry.centroid(
        topology, heightmap.surface_z,
        (float(max(z, 1)) for z in heightmap.surface_z.values()), anchor,
    )


def water_step_from_segment(a: Cell, b: Cell, land_centroid: tuple[float, float], *,
                            topology: WorldTopology) -> Cell:
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return (0, 0)
    steps = [
        (0 if px == 0 else (1 if px > 0 else -1),
         0 if py == 0 else (1 if py > 0 else -1))
        for px, py in [(-dy, dx), (dy, -dx)]
    ]
    land = topology_geometry.unrolled_images(topology, land_centroid, anchor=(mx, my))[0].coord
    # Local normal orientation in the segment frame, not a canonical-world metric.
    return max(steps, key=lambda step: (mx - land[0]) * step[0] + (my - land[1]) * step[1])


@dataclass(frozen=True)
class _CoastSegment:
    a: Cell
    b: Cell
    step: Cell
    cells: tuple[Cell, ...]

    def side(self, result: topology_geometry.SegmentProjection) -> _WaterSide:
        point = int(result.image.coord[0]), int(result.image.coord[1])
        # Both points are already in this owning segment's unrolled frame.
        k = min(self.cells, key=lambda k: (
            (point[0] - k[0]) ** 2 + (point[1] - k[1]) ** 2,
            -((point[0] - k[0]) * self.step[0] + (point[1] - k[1]) * self.step[1]),
            k[1], k[0],
        ))
        dot = (point[0] - k[0]) * self.step[0] + (point[1] - k[1]) * self.step[1]
        return _WaterSide(k, self.step, dot, result.projection, point)


@dataclass(frozen=True)
class _WaterSide:
    coast: Cell
    step: Cell
    dot: int
    projection: Fraction
    point: Cell


class CoastlineWaterSide:
    """One owning segment supplies K, n(K), and t; ties prefer max dot."""

    def __init__(self, coastline_cells: set[Cell], segments: list[Segment],
                 land_centroid: tuple[float, float], *, topology: WorldTopology) -> None:
        self.topology = topology
        self.coastline_cells = coastline_cells
        self._canonical_coast = {canonical for cell in coastline_cells
                                 if (canonical := topology.canonicalize(*cell)) is not None}
        self._segments: list[_CoastSegment] = []
        self._cache: dict[Cell, _WaterSide | None] = {}
        for a, b in segments:
            cells = {raw for raw in rasterize_segments([(a, b)])
                     if topology.canonicalize(*raw) in self._canonical_coast}
            if not cells:
                continue
            step = water_step_from_segment(a, b, land_centroid, topology=topology)
            if a == b:
                # Only a point coastline uses the centroid fallback.
                land = topology_geometry.unrolled_images(topology, land_centroid, anchor=a)[0].coord
                away = max(topology_geometry.neighbors4_unrolled(a), key=lambda c: (
                    (c[0] - a[0]) * (a[0] - land[0]) + (c[1] - a[1]) * (a[1] - land[1])
                ))
                step = away[0] - a[0], away[1] - a[1]
            self._segments.append(_CoastSegment(
                a, b, step, tuple(sorted(cells, key=lambda c: (c[1], c[0]))),
            ))

    def at(self, cell: Cell) -> _WaterSide | None:
        if cell in self._cache:
            return self._cache[cell]
        nearest: Fraction | None = None
        selected: _WaterSide | None = None
        for segment in self._segments:
            result = topology_geometry.nearest_on_segment(
                self.topology, cell, segment.a, segment.b,
                tie_breaker=lambda result: -segment.side(result).dot,
            )
            distance = result.distance2
            if nearest is not None and distance > nearest:
                continue
            candidate = segment.side(result)
            dot, k = candidate.dot, candidate.coast
            if (nearest is None or distance < nearest or selected is None
                    or (dot, -k[1], -k[0]) > (selected.dot, -selected.coast[1], -selected.coast[0])):
                selected = candidate
            nearest = distance
        self._cache[cell] = selected
        return selected

    def contains(self, cell: Cell, *, bounded: bool) -> bool:
        side = self.at(cell)
        return (side is not None and side.dot > 0
                and (not bounded or 0 <= side.projection <= 1))

    def seeds(self, passable: Callable[[Cell], bool]) -> set[Cell]:
        seeds: set[Cell] = set()
        can_step = canonical_passable(self.topology, passable)
        for k in sorted(self.coastline_cells, key=lambda c: (c[1], c[0])):
            side = self.at(k)
            if side is None:
                continue
            seed = side.point[0] + side.step[0], side.point[1] + side.step[1]
            if can_step(seed) and self.contains(seed, bounded=False):
                seeds.add(seed)
        return seeds

    def land_shore(self, passable: Callable[[Cell], bool]) -> set[Cell]:
        land: set[Cell] = set()
        can_step = canonical_passable(self.topology, passable)
        for k in self.coastline_cells:
            if not can_step(k):
                continue
            for neighbor in topology_geometry.neighbors4_unrolled(k):
                canonical = self.topology.canonicalize(*neighbor)
                if canonical is None or canonical in self._canonical_coast or not passable(canonical):
                    continue
                side = self.at(neighbor)
                if side is not None and side.dot < 0:
                    land.add(canonical)
        return land


def water_side_footprint(geometry: CoastlineWaterSide, *, bounded: bool,
                         passable: Callable[[Cell], bool]) -> dict[Cell, int]:
    """Reachable footprint with 1-based distance; passability belongs to caller."""
    dist: dict[Cell, int] = {}
    queue: deque[tuple[Cell, int]] = deque()
    topology = geometry.topology
    can_step = canonical_passable(topology, passable)
    for seed in sorted(geometry.seeds(passable), key=lambda c: (c[1], c[0])):
        canonical = topology.canonicalize(*seed)
        if canonical is not None and canonical not in dist and geometry.contains(seed, bounded=bounded):
            dist[canonical] = 1
            queue.append((seed, 1))
    while queue:
        cell, distance = queue.popleft()
        for neighbor in topology_geometry.neighbors4_unrolled(cell):
            canonical = topology.canonicalize(*neighbor)
            if canonical is None or canonical in dist or not can_step(neighbor):
                continue
            if geometry.contains(neighbor, bounded=bounded):
                dist[canonical] = distance + 1
                queue.append((neighbor, distance + 1))
    return dist
