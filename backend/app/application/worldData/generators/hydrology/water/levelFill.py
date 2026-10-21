"""One strict level-fill implementation for single and labelled multi-source water."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from heapq import heappop, heappush

from app.dataModel.topology.topologyGeometry import canonical_neighbors4
from app.dataModel.topology.worldTopology import Coord, WorldTopology


@dataclass(frozen=True)
class LevelFill:
    cells: frozenset[Coord]
    floor_z: int | None

    @property
    def area(self) -> int:
        return len(self.cells)


@dataclass(frozen=True)
class LevelFillSource:
    owner: int
    water_body_uid: str  # Opaque source UID, used only to resolve equal-distance claims.
    seeds: tuple[Coord, ...]
    level: int


@dataclass(frozen=True)
class LabelledLevelFill:
    owners: dict[Coord, int]
    areas: dict[int, int]
    floors: dict[int, int]


def labelled_level_fill(surface_z: Mapping[Coord, int], sources: Sequence[LevelFillSource],
                         topology: WorldTopology) -> LabelledLevelFill:
    """Final effective-level fill; height and cell ownership are never guessed.

    Each settled cell emits at most four frontier claims. Ties use distance,
    source UID and canonical (y,x), independently of input/hash iteration.
    Area and floor statistics are collected in this same pass.
    """
    owners: dict[Coord, int] = {}
    areas: dict[int, int] = {}
    floors: dict[int, int] = {}
    levels = {source.owner: source.level for source in sources}
    if len(levels) != len(sources):
        raise ValueError("duplicate water fill owner")
    heap = []
    queued: set[tuple[Coord, int]] = set()
    for source in sources:
        for cell in source.seeds:
            if cell not in surface_z:
                raise ValueError(f"unresolved water: missing seed elevation at {cell}")
            if surface_z[cell] < source.level and (cell, source.owner) not in queued:
                heappush(heap, (0, source.water_body_uid, cell[1], cell[0], source.owner))
                queued.add((cell, source.owner))
    while heap:
        distance, uid, y, x, owner = heappop(heap)
        cell = (x, y)
        if cell in owners:
            continue
        owners[cell] = owner
        areas[owner] = areas.get(owner, 0) + 1
        floors[owner] = min(floors.get(owner, surface_z[cell]), surface_z[cell])
        for neighbor in canonical_neighbors4(topology, cell):
            if neighbor not in surface_z:
                raise ValueError(f"unresolved water: missing rim elevation at {neighbor}")
            if (neighbor not in owners and (neighbor, owner) not in queued
                    and surface_z[neighbor] < levels[owner]):
                queued.add((neighbor, owner))
                heappush(heap, (distance + 1, uid, neighbor[1], neighbor[0], owner))
    return LabelledLevelFill(owners, areas, floors)


def level_fill(surface_z: Mapping[Coord, int], seeds: Iterable[Coord], level: int,
               topology: WorldTopology) -> LevelFill:
    fill = labelled_level_fill(surface_z, (LevelFillSource(0, "", tuple(seeds), level),), topology)
    return LevelFill(frozenset(fill.owners), fill.floors.get(0))
