"""Region shape/claim → light or fine cells (tz_map_light_bake, regions).

Shapes remain in unrolled fine coordinates. Only topology canonicalizes;
membership, edge falloff and density are shared by both sampling grids.
"""

from collections import deque
from collections.abc import Callable, Iterator
from functools import partial

from app.application.worldData.masks.footprint import LightCellRef
from app.application.worldData.masks.regionRasterContext import (
    ClaimSeed, RasterWorld, RegionClaim, RegionRasterContext,
)
from app.application.worldData.masks.regionRasterNoise import boundary_depth, smooth_field
from app.application.worldData.pack.bake.lightGrid.coords import light_cell_center_m
from app.dataModel.spatial.facing import CARDINAL_FACINGS
from app.dataModel.spatial.regionShape import Bounds, Point, RegionShape
from app.dataModel.worldPack.wire.worldTopology import Coord, WorldTopology
from app.ids import RegionRngChannel, UidKind, seed_rng, seed_root, seeded_u01


def _density(root: str, ctx: RegionRasterContext, coord: Coord) -> bool:
    density = ctx.spec.density
    return density >= 1 or (density > 0 and seeded_u01(
        root, UidKind.REGION, channel=RegionRngChannel.DENSITY,
        uid=ctx.region_uid, x=coord[0], y=coord[1],
    ) < density)


def _membership(shape: RegionShape, root: str, ctx: RegionRasterContext,
                topology: WorldTopology) -> Callable[[Point, Coord], bool]:
    edge = shape.edge_noise
    noise = None
    if edge is not None and edge.amplitude:
        def sample(**keys: int) -> float:
            return seed_rng(root, UidKind.REGION, channel=RegionRngChannel.EDGE,
                            uid=ctx.region_uid, **keys).random()
        noise = smooth_field(sample, edge.scale, topology)

    def contains(raw: Point, canonical: Coord) -> bool:
        if not shape.contains(*raw):
            return False
        if noise is not None and boundary_depth(shape, *raw) < edge.amplitude * noise(*canonical):
            return False
        return _density(root, ctx, canonical)

    return contains


def _fine_samples(bbox: Bounds, topology: WorldTopology) -> Iterator[tuple[Point, Coord]]:
    x_min, y_min, x_max, y_max = bbox
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            coord = topology.canonicalize(x, y)
            if coord is not None:
                yield (x, y), coord


def _light_samples(bbox: Bounds, ctx: RegionRasterContext,
                   topology: WorldTopology) -> Iterator[tuple[Point, Coord, LightCellRef]]:
    """Lift canonical L0 centers into each intersecting unrolled macro-tile.

    Canonicalizing tile endpoints also handles reflected sphere rows. No
    mode switch or wrap arithmetic belongs to the rasterizer.
    """
    x_min, y_min, x_max, y_max = bbox
    scale = ctx.scale
    tile = scale.tile_m
    for gx in range(x_min // tile, x_max // tile + 1):
        for gy in range(y_min // tile, y_max // tile + 1):
            ox, oy = gx * tile, gy * tile
            start = topology.canonicalize(ox, oy)
            end = topology.canonicalize(ox, oy + tile - 1)
            if start is None or end is None:
                continue
            cgx, cgy = start[0] // tile, min(start[1], end[1]) // tile
            sign_y = 1 if end[1] >= start[1] else -1
            for tx in range(scale.side):
                for ty in range(scale.side):
                    coord = light_cell_center_m(cgx, cgy, tx, ty, scale)
                    raw = ox + coord[0] - start[0], oy + sign_y * (coord[1] - start[1])
                    if x_min <= raw[0] <= x_max and y_min <= raw[1] <= y_max:
                        yield raw, coord, LightCellRef(cgx, cgy, tx, ty)


def rasterize_light(shape: RegionShape, world: RasterWorld,
                    spec_ctx: RegionRasterContext) -> frozenset[LightCellRef]:
    topology = spec_ctx.fine_topology()
    contains = _membership(shape, seed_root(world), spec_ctx, topology)
    samples = _light_samples(shape.bbox(), spec_ctx, topology)
    return frozenset(cell for raw, coord, cell in samples if contains(raw, coord))


def rasterize_fine(shape: RegionShape, world: RasterWorld,
                   spec_ctx: RegionRasterContext) -> set[Coord]:
    topology = spec_ctx.fine_topology()
    contains = _membership(shape, seed_root(world), spec_ctx, topology)
    samples = _fine_samples(shape.bbox(), topology)
    return {coord for raw, coord in samples if contains(raw, coord)}


def claim_owners(claim: RegionClaim, root: str,
                  topology: WorldTopology) -> dict[Coord, ClaimSeed]:
    """Bounded graph distance, then w = radius-distance + coherent noise.

    All candidates are evaluated before selection. Noise cannot stop graph
    exploration, and the caller's bake scope never truncates competition.
    Equal scores use canonical seed order, independent of input order.
    """
    seeds = set()
    for seed in claim.seeds:
        coord = topology.canonicalize(*seed.coord)
        if coord is not None:
            seeds.add(ClaimSeed(coord, seed.region_uid))
    winners: dict[Coord, ClaimSeed] = {}
    scores: dict[Coord, float] = {}
    for seed in sorted(seeds):
        sample = partial(seeded_u01, root, UidKind.REGION,
                         channel=RegionRngChannel.CLAIM, seed_xy=seed.coord)
        noise = smooth_field(sample, claim.noise.scale, topology)
        queue = deque([(seed.coord, 0)])
        seen = {seed.coord}
        while queue:
            coord, distance = queue.popleft()
            score = claim.max_radius - distance
            if claim.noise.amplitude:
                score += claim.noise.amplitude * (2 * noise(*coord) - 1)
            if score >= 0 and (coord not in scores or score > scores[coord]):
                winners[coord], scores[coord] = seed, score
            if distance == claim.max_radius:
                continue
            for facing in CARDINAL_FACINGS:
                neighbor = topology.neighbor(*coord, facing)
                if neighbor is not None and neighbor.coord not in seen:
                    seen.add(neighbor.coord)
                    queue.append((neighbor.coord, distance + 1))
    return winners


class ClaimOwnersIndex:
    """One ``claim_owners`` BFS per claim, shared by every sibling region.

    Build once per ``RegionClaim`` per bake/refine pass; rasterize calls take
    the index, so membership never re-runs the search per region or tile.
    """

    def __init__(self, claim: RegionClaim, root: str,
                 topology: WorldTopology) -> None:
        self.claim = claim
        self.owners = claim_owners(claim, root, topology)


def _claim_membership(index: ClaimOwnersIndex, world: RasterWorld,
                     spec_ctx: RegionRasterContext, *, scope: Bounds | None = None) -> set[Coord]:
    """Cells won by this UID. Scope filters output only; it cannot alter w."""
    root = seed_root(world)
    return {coord for coord, seed in index.owners.items()
            if seed.region_uid == spec_ctx.region_uid
            and (scope is None or scope[0] <= coord[0] <= scope[2] and scope[1] <= coord[1] <= scope[3])
            and _density(root, spec_ctx, coord)}


def rasterize_claim_fine(index: ClaimOwnersIndex, world: RasterWorld,
                         spec_ctx: RegionRasterContext, *, scope: Bounds | None = None) -> set[Coord]:
    return _claim_membership(index, world, spec_ctx, scope=scope)


def rasterize_claim_light(index: ClaimOwnersIndex, world: RasterWorld,
                          spec_ctx: RegionRasterContext, *, scope: Bounds | None = None) -> frozenset[LightCellRef]:
    coords = _claim_membership(index, world, spec_ctx, scope=scope)
    scale = spec_ctx.scale
    cells = set()
    for coord in coords:
        gx, lx = divmod(coord[0], scale.tile_m)
        gy, ly = divmod(coord[1], scale.tile_m)
        tx = min(lx // scale.light_m, scale.side - 1)
        ty = min(ly // scale.light_m, scale.side - 1)
        if coord == light_cell_center_m(gx, gy, tx, ty, scale):
            cells.add(LightCellRef(gx, gy, tx, ty))
    return frozenset(cells)
