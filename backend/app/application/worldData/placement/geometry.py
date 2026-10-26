"""Footprint comparisons through WorldTopology; authored geometry stays unchanged."""

from app.dataModel.placement import PlacementFootprint
from app.dataModel.spatial.facing import CARDINAL_FACINGS
from app.dataModel.topology import topologyGeometry
from app.dataModel.topology.worldTopology import Coord, WorldTopology


class PlacementGeometry:
    def __init__(self, topology: WorldTopology) -> None:
        self.topology = topology
        self._canonical: dict[PlacementFootprint, frozenset[Coord] | None] = {}
        self._boundaries: dict[PlacementFootprint, frozenset[Coord]] = {}

    def canonical_cells(self, footprint: PlacementFootprint) -> frozenset[Coord] | None:
        if footprint not in self._canonical:
            cells = [self.topology.canonicalize(*cell) for cell in footprint.cells]
            self._canonical[footprint] = None if None in cells else frozenset(cells)
        return self._canonical[footprint]

    def cells(self, footprint: PlacementFootprint) -> frozenset[Coord]:
        cells = self.canonical_cells(footprint)
        if cells is None:
            raise ValueError("footprint outside planar topology must be rejected before comparison")
        return cells

    def boundary(self, footprint: PlacementFootprint) -> frozenset[Coord]:
        if footprint not in self._boundaries:
            cells = self.cells(footprint)
            self._boundaries[footprint] = frozenset(
                cell for cell in cells if any(
                    (neighbor := self.topology.neighbor(*cell, facing)) is None or neighbor.coord not in cells
                    for facing in CARDINAL_FACINGS))
        return self._boundaries[footprint]

    @staticmethod
    def z_overlap(left: PlacementFootprint, right: PlacementFootprint) -> bool:
        return (left.z_min is None or right.z_min is None
                or (left.z_min <= right.z_max and right.z_min <= left.z_max))

    def collides(self, left: PlacementFootprint, right: PlacementFootprint) -> bool:
        return self.z_overlap(left, right) and not self.cells(left).isdisjoint(self.cells(right))

    def contains(self, outer: PlacementFootprint, inner: PlacementFootprint) -> bool:
        if not self.cells(inner) <= self.cells(outer):
            return False
        if outer.z_min is None:
            return True
        return (inner.z_min is not None
                and outer.z_min <= inner.z_min and inner.z_max <= outer.z_max)

    def supports(self, support: PlacementFootprint, child: PlacementFootprint) -> bool:
        return (support.z_max is not None and child.z_min is not None
                and child.z_min == support.z_max + 1
                and self.cells(child) <= self.cells(support))

    def connected(self, left: PlacementFootprint, right: PlacementFootprint) -> bool:
        if (left.z_min is not None and right.z_min is not None
                and (left.z_min > right.z_max + 1 or right.z_min > left.z_max + 1)):
            return False
        left_cells, right_cells = self.cells(left), self.cells(right)
        if not left_cells.isdisjoint(right_cells):
            return True
        return any((neighbor := self.topology.neighbor(*cell, facing)) is not None
                   and neighbor.coord in right_cells
                   for cell in left_cells for facing in CARDINAL_FACINGS)

    def shared_boundary(self, left: PlacementFootprint, right: PlacementFootprint) -> bool:
        shared = self.cells(left) & self.cells(right)
        return bool(shared) and shared <= self.boundary(left) & self.boundary(right)

    def separated(self, left: PlacementFootprint, right: PlacementFootprint, *, min_xy: int, min_z: int) -> bool:
        if left.z_min is not None and right.z_min is not None and not self.z_overlap(left, right):
            empty_levels = max(left.z_min - right.z_max - 1, right.z_min - left.z_max - 1)
            if empty_levels >= min_z:
                return True
        left_cells, right_cells = self.cells(left), self.cells(right)
        if not left_cells.isdisjoint(right_cells):
            return False
        if min_xy == 0:
            return True
        threshold2 = (min_xy + 1) ** 2
        return all(topologyGeometry.dist2(self.topology, a, b) >= threshold2
                   for a in left_cells for b in right_cells)
