"""Detailed bake job keys — suffix on L0 tile uid, not a tile job.

Format SoT: ``PackJobUid``. Owner of ``tile_edge`` = grid neighbor (no AABB wrap);
canonical side is the owner's outward compact letter so both tiles share one key.
"""

from __future__ import annotations

from app.dataModel.spatial.facing import (
    CARDINAL_FACINGS,
    COMPACT_LETTER,
    Facing,
    parse_facing,
)
from app.dataModel.worldPack.packJobUid import PackJobUid


def chunk_job_uid(
    *,
    world_seed: str,
    tile_gx: int,
    tile_gy: int,
    cx: int,
    cy: int,
) -> str:
    return PackJobUid.canonical_defaults().chunk_uid(
        world_seed=world_seed,
        tile_gx=tile_gx,
        tile_gy=tile_gy,
        cx=cx,
        cy=cy,
    )


def interior_grade_site(
    *,
    tile_gx: int,
    tile_gy: int,
    cx: int,
    cy: int,
    k: int,
) -> str:
    """Hashed site_id for an isolated interior ribbon (not the chunk job uid)."""
    return PackJobUid.canonical_defaults().interior_site(
        tile_gx=tile_gx, tile_gy=tile_gy, cx=cx, cy=cy, k=k,
    )


def face_grade_site(tile_gx: int, tile_gy: int, face_wire: str) -> str:
    return PackJobUid.canonical_defaults().face_site(tile_gx, tile_gy, face_wire)


def front_grade_site(context: str, x: int, y: int, facing: str) -> str:
    """Discovered-front pick site — ``PackJobUid.grade_front_site``, not a raw f-string."""
    return PackJobUid.canonical_defaults().grade_front_site(context, x, y, facing)


def parse_tile_edge_side(side: str | Facing) -> Facing:
    facing = side if isinstance(side, Facing) else parse_facing(side)
    if facing is None or facing not in CARDINAL_FACINGS:
        raise ValueError(f"tile_edge side must be cardinal, got {side!r}")
    return facing


def canonical_tile_edge(
    tile_gx: int,
    tile_gy: int,
    side: str | Facing,
) -> tuple[int, int, Facing]:
    """Owner tile + owner-outward facing for a rim of ``(tile_gx, tile_gy)``."""
    facing = parse_tile_edge_side(side)
    if facing is Facing.EAST:
        return tile_gx, tile_gy, Facing.EAST
    if facing is Facing.WEST:
        return tile_gx - 1, tile_gy, Facing.EAST
    if facing is Facing.NORTH:
        return tile_gx, tile_gy, Facing.NORTH
    return tile_gx, tile_gy - 1, Facing.NORTH


def tile_edge_job_uid(
    *,
    world_seed: str,
    tile_gx: int,
    tile_gy: int,
    side: str | Facing,
) -> str:
    owner_gx, owner_gy, owner_side = canonical_tile_edge(tile_gx, tile_gy, side)
    return PackJobUid.canonical_defaults().tile_edge_uid(
        world_seed=world_seed,
        owner_gx=owner_gx,
        owner_gy=owner_gy,
        compact_side=COMPACT_LETTER[owner_side],
    )
