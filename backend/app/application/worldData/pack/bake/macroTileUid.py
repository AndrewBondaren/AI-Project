"""L0 macro-tile job uid — ``full_bake`` / light tile identity.

Format SoT: ``PackJobUid``. This module only reads world → seed namespace.
"""

from __future__ import annotations

from app.application.worldData.ids import seed_root
from app.dataModel.worldPack.packJobUid import PackJobUid
from app.db.models.world import World


def pack_job_seed(world: World) -> str:
    """Pack job-uid namespace. Not climate ``world_seed`` (int) and not relief pick."""
    return seed_root(world)


def macro_tile_site(tile_gx: int, tile_gy: int) -> str:
    return PackJobUid.canonical_defaults().tile_site(tile_gx, tile_gy)


def macro_tile_uid(*, world_seed: str, tile_gx: int, tile_gy: int) -> str:
    return PackJobUid.canonical_defaults().tile_uid(
        world_seed=world_seed, tile_gx=tile_gx, tile_gy=tile_gy,
    )
