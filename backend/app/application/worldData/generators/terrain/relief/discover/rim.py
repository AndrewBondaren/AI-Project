"""C39 leftover rims: bucket[z], seed, 8-flood from the rim.

Does not walk fronts or write occ/seam. Plugin decides body membership.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    EIGHT_DELTAS,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    VertexBodyPlugin,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    ReliefSurface,
    ReliefVertices,
    cell_z,
)


def seed_rim(
    xy: Coord,
    surface: ReliefSurface,
    vertices: ReliefVertices,
) -> bool:
    """C39 uncovered rim: free cell with a free 8-neighbor downhill.

    A shared-pit ``seam`` neighbor still counts: several vertices may shoot
    into the depression. Occupied corridor (``occ``) does not.
    """
    if not vertices.is_free(xy):
        return False
    z = cell_z(surface, xy)
    if z is None:
        return False
    x, y = xy
    for dx, dy in EIGHT_DELTAS:
        nb = (x + dx, y + dy)
        zn = cell_z(surface, nb)
        if zn is None or zn >= z:
            continue
        ni = vertices.index(nb[0], nb[1])
        if ni is None:
            return True
        if vertices.occ[ni] == 0:
            return True
    return False


@dataclass(frozen=True, slots=True)
class RimStage:
    """C39: leftover rims on the bake grid."""

    surface: ReliefSurface
    vertices: ReliefVertices
    plugins: Sequence[VertexBodyPlugin]

    def buckets_high_to_low(self) -> list[tuple[int, list[Coord]]]:
        buckets: dict[int, list[Coord]] = defaultdict(list)
        verts = self.vertices
        surface = self.surface
        for ly in range(verts.height):
            for lx in range(verts.width):
                xy = (verts.origin_x + lx, verts.origin_y + ly)
                z = cell_z(surface, xy)
                if z is None:
                    continue
                buckets[z].append(xy)
        return [(z, buckets[z]) for z in sorted(buckets, reverse=True)]

    def is_seed(self, xy: Coord) -> bool:
        return seed_rim(xy, self.surface, self.vertices)

    def plugin_for(self, xy: Coord) -> VertexBodyPlugin | None:
        for plugin in self.plugins:
            if plugin.claims(xy, self.surface):
                return plugin
        return None

    def flood(self, start: Coord, plugin: VertexBodyPlugin) -> dict[Coord, int]:
        """8-flood same z from this rim only — not a full same-z CC of the tile."""
        surface = self.surface
        vertices = self.vertices
        z_body = cell_z(surface, start)
        if z_body is None:
            return {}
        body: dict[Coord, int] = {}
        q: deque[Coord] = deque([start])
        seen: set[Coord] = set()
        while q:
            xy = q.popleft()
            if xy in seen:
                continue
            seen.add(xy)
            i = vertices.index(xy[0], xy[1])
            if i is None:
                continue
            if vertices.occ[i] != 0 or vertices.seam[i] != 0:
                continue
            if vertices.at_grid[i] != 0:
                continue
            if vertices.facing_bits[i] != 0:
                continue
            z = cell_z(surface, xy)
            if z != z_body:
                continue
            if not plugin.flood_member(xy, z_body, surface):
                continue
            body[xy] = z_body
            x, y = xy
            for dx, dy in EIGHT_DELTAS:
                q.append((x + dx, y + dy))
        if not plugin.accept_flood(body, surface):
            return {}
        return body
