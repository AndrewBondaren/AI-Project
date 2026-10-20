"""Same-kind connected components, canonical owner and relative sublocation facings."""

from collections import deque
from dataclasses import dataclass

from app.application.worldData.generators.terrain.landcover.autoresolve.seedGrid import WorldSeed, seed_adjacency
from app.application.worldData.generators.terrain.landcover.types import Sublocation
from app.dataModel.spatial.facing import GRID_DELTA_TO_FACING, GRID_OUTWARD_DELTA, opposite
from app.dataModel.spatial.regionShape import Point
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.topology.worldTopology import WorldTopology
from app.ids.regionIdentity import region_uid


@dataclass(frozen=True)
class CoverageSeed:
    seed: WorldSeed
    target_key: str


@dataclass(frozen=True)
class SeedRegion:
    region_uid: str
    target_key: str
    seeds: tuple[CoverageSeed, ...]
    sublocations: tuple[Sublocation, ...]


def merge_sublocations(seeds: tuple[CoverageSeed, ...], topology: WorldTopology,
                       policy: LandcoverRegionsCategoryPolicy, world_uid: str) -> tuple[SeedRegion, ...]:
    by_coord = {seed.seed.coord: seed for seed in seeds}
    graph = seed_adjacency(tuple(seed.seed for seed in seeds), topology, policy)
    # Undirected connectivity, including reflected topology edges.
    for coord, neighbors in list(graph.items()):
        for other in list(neighbors):
            if coord not in graph[other]:
                graph[other][coord] = opposite(neighbors[other])
    unseen, regions = set(by_coord), []
    while unseen:
        owner = min(unseen)
        target = by_coord[owner].target_key
        queue, offsets = deque([owner]), {owner: (0, 0)}
        unseen.remove(owner)
        while queue:
            coord = queue.popleft()
            for other, facing in sorted(graph[coord].items()):
                if other not in unseen or by_coord[other].target_key != target:
                    continue
                unseen.remove(other)
                dx, dy = GRID_OUTWARD_DELTA[facing]
                ox, oy = offsets[coord]
                offsets[other] = ox + dx, oy + dy
                queue.append(other)
        coords = sorted(offsets)
        cx = sum(offsets[c][0] for c in coords) / len(coords)
        cy = sum(offsets[c][1] for c in coords) / len(coords)
        sublocations = []
        for coord in coords:
            x, y = offsets[coord]
            delta = (x > cx) - (x < cx), (y > cy) - (y < cy)
            sublocations.append(Sublocation(coord, region_uid(world_uid, seed_xy=coord),
                                            GRID_DELTA_TO_FACING.get(delta)))
        regions.append(SeedRegion(region_uid(world_uid, region_seed_xy=owner), target,
                                  tuple(by_coord[c] for c in coords), tuple(sublocations)))
    return tuple(regions)
