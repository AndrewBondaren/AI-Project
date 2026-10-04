"""Pure wall classifier — tz_building_generator.md §8.7.1.

Assigns provenance (exterior shell / interior partition) and adjacent rooms
to every physical wall cell, reproducing exactly the wall set that
`pass3_interior_walls` produces today — including open-shaft partition
removal. No material choice, no cells, no RNG: geometry in → typed
`WallRegion` list out. One cell belongs to exactly one region.
"""
from collections import deque

from app.application.worldData.generators.structure.cellBuilder import (
    _interior, _NEIGHBOURS, _open_shaft_perimeter,
)
from app.application.worldData.generators.structure.room.roomInstance import (
    _RoomInstance,
)
from app.dataModel.locations.structure.wallRegion import (
    WallProvenance, WallRegion,
)


def _components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    """4-connected components; seeds in sorted order → deterministic."""
    remaining = set(cells)
    out: list[set[tuple[int, int]]] = []
    while remaining:
        seed = min(remaining)
        comp = {seed}
        remaining.discard(seed)
        frontier = deque([seed])
        while frontier:
            x, y = frontier.popleft()
            for dx, dy in _NEIGHBOURS:
                nxt = (x + dx, y + dy)
                if nxt in remaining:
                    remaining.discard(nxt)
                    comp.add(nxt)
                    frontier.append(nxt)
        out.append(comp)
    return out


def classify_wall_regions(
    rooms: list[_RoomInstance],
    z_min: int,
    z_max: int,
) -> list[WallRegion]:
    """Classify the physical wall cells of `rooms` into typed regions.

    A wall cell is EXTERIOR iff any 4-neighbour lies outside every footprint
    (open air or unused volume — gaps, shape notches, enclosed courtyards);
    INTERIOR otherwise. Candidates are the non-shaft rooms whose interior is
    adjacent to the cell, sorted by uid_key — the caller-deterministic order
    required by the §11.3 first-candidate tie-break.
    """
    placed = [r for r in rooms if r.placed]
    opened = _open_shaft_perimeter(placed)

    union_fp: set[tuple[int, int]] = set()
    wall_cells: set[tuple[int, int]] = set()
    interiors: dict[str, set[tuple[int, int]]] = {}
    for r in placed:
        fp = r.get_footprint()
        union_fp |= fp
        wall_cells |= fp - _interior(fp)
        if not r.is_shaft:
            interiors[r.uid_key] = _interior(fp)
    wall_cells -= opened

    groups: dict[tuple[WallProvenance, tuple[str, ...]], set[tuple[int, int]]] = {}
    for x, y in wall_cells:
        if any((x + dx, y + dy) not in union_fp for dx, dy in _NEIGHBOURS):
            signature = (WallProvenance.EXTERIOR, ())
        else:
            keys = tuple(sorted(
                key for key, cells in interiors.items()
                if any((x + dx, y + dy) in cells for dx, dy in _NEIGHBOURS)
            ))
            signature = (WallProvenance.INTERIOR, keys)
        groups.setdefault(signature, set()).add((x, y))

    regions: list[WallRegion] = []
    for (provenance, keys), cells in groups.items():
        for component in _components(cells):
            regions.append(WallRegion(
                cells=frozenset(component), z_min=z_min, z_max=z_max,
                provenance=provenance, room_keys=keys,
            ))
    regions.sort(key=lambda r: (min(r.cells), r.provenance.value, r.room_keys))
    return regions
