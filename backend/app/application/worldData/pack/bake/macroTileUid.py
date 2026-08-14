"""L0 macro-tile job uid — ``full_bake`` / light tile identity.

Format SoT: ``PackJobUid``. This module only reads world → seed namespace.
"""

from __future__ import annotations

from app.dataModel.worldPack.packJobUid import PackJobUid
from app.db.models.world import World


def pack_job_seed(world: World) -> str:
    """Pack job-uid namespace. Not climate ``world_seed`` (int) and not relief pick."""
    uid = getattr(world, "world_uid", None)
    if not uid:
        raise ValueError("pack_job_seed requires world.world_uid")
    return str(uid)


def macro_tile_site(tile_gx: int, tile_gy: int) -> str:
    return PackJobUid.canonical_defaults().tile_site(tile_gx, tile_gy)


def macro_tile_uid(*, world_seed: str, tile_gx: int, tile_gy: int) -> str:
    return PackJobUid.canonical_defaults().tile_uid(
        world_seed=world_seed, tile_gx=tile_gx, tile_gy=tile_gy,
    )
