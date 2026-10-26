"""One jittered seed per world lattice cell; bake tiles are never an input."""

from collections import deque
from dataclasses import dataclass

from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing, opposite
from app.dataModel.spatial.regionShape import Point
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.topology.worldTopology import WorldTopology
from app.ids import RegionRngChannel, UidKind, seeded_u01


@dataclass(frozen=True, order=True)
class WorldSeed:
    coord: Point
    lattice: Point


def generate_seeds(root: str, topology: WorldTopology,
                   policy: LandcoverRegionsCategoryPolicy) -> tuple[WorldSeed, ...]:
    """topology is in fine cells. A single RNG value selects a uniform 2-D offset."""
    bounds, step = topology.bounds, policy.seed_spacing
    seeds = []
    for sx in range(bounds.x_min // step, bounds.x_max // step + 1):
        for sy in range(bounds.y_min // step, bounds.y_max // step + 1):
            x0, x1 = max(sx * step, bounds.x_min), min((sx + 1) * step - 1, bounds.x_max)
            y0, y1 = max(sy * step, bounds.y_min), min((sy + 1) * step - 1, bounds.y_max)
            width, height = x1 - x0 + 1, y1 - y0 + 1
            value = seeded_u01(root, UidKind.REGION, channel=RegionRngChannel.SEED, sx=sx, sy=sy)
            dx, dy = divmod(min(int(value * width * height), width * height - 1), height)
            coord = topology.canonicalize(x0 + dx, y0 + dy)
            seeds.append(WorldSeed(coord, (sx, sy)))
    return tuple(sorted(seeds))


def _within_radius(start: Point, target: Point, topology: WorldTopology, radius: int) -> bool:
    queue, seen = deque([(start, 0)]), {start}
    while queue:
        coord, distance = queue.popleft()
        if coord == target:
            return True
        if distance == radius:
            continue
        for facing in sorted(CARDINAL_FACINGS):
            neighbor = topology.neighbor(*coord, facing)
            if neighbor is not None and neighbor.coord not in seen:
                seen.add(neighbor.coord)
                queue.append((neighbor.coord, distance + 1))
    return False


def seed_adjacency(seeds: tuple[WorldSeed, ...], topology: WorldTopology,
                   policy: LandcoverRegionsCategoryPolicy) -> dict[Point, dict[Point, Facing]]:
    """Adjacent lattice cells through topology; edges must fit the graph-distance cap."""
    by_lattice = {seed.lattice: seed for seed in seeds}
    graph = {seed.coord: {} for seed in seeds}
    for seed in seeds:
        for initial_facing in sorted(CARDINAL_FACINGS):
            coord, facing, seen = seed.coord, initial_facing, set()
            while (coord, facing) not in seen:
                seen.add((coord, facing))
                neighbor = topology.neighbor(*coord, facing)
                if neighbor is None:
                    break
                coord = neighbor.coord
                if neighbor.invert_dy:
                    facing = opposite(facing)
                lattice = coord[0] // policy.seed_spacing, coord[1] // policy.seed_spacing
                if lattice == seed.lattice:
                    continue
                other = by_lattice.get(lattice)
                if other is not None and _within_radius(seed.coord, other.coord, topology, policy.max_radius):
                    graph[seed.coord][other.coord] = initial_facing
                break
    return graph
