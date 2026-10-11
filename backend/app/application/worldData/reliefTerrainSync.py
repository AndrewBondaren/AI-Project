"""R34 ``terrain_registry`` upsert — shared by legacy import and pack remap.

``tz_terrain_relief`` R34: bringing a relief template into a world may
upsert *missing* ``system_terrain`` keys from the canonical engine set —
existing rows are never overwritten. Single logic source for the
world-import service (bundle legacy path) and the relief pack adapter
(``instantiate_pack`` world-side remap, plan
``libpack-t2-relief-import-instantiate`` step 1).

Missing is judged on the **stored** rows, not the resolved POJO:
``resolve_registry_list_world`` auto-completes canonical entries on read
(T-29 overlay), so a resolved scan would never find a canonical key
absent — the raw-column scan mirrors the pointer mixin's convention.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.application.worldData.generators.terrain.relief.log.log import (
    relief_warning,
)
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

if TYPE_CHECKING:
    from app.db.models.world import World


def missing_terrain_entries(world: World, needed: Iterable[str]) -> list:
    """Pure R34 projection; emission and persistence belong to the caller."""
    have = {row.get("system_terrain") for row in world.terrain_registry or [] if isinstance(row, dict)}
    canon = {e.system_terrain: e for e in WorldTerrainRegistry.canonical_engine().root}
    return [canon[key] for key in sorted(set(needed)) if key not in have and key in canon]


def merge_missing_terrain_entries(
    world: World,
    needed: Iterable[str],
    *,
    source: str,
    template_uid: str | None = None,
    system_name: str | None = None,
) -> list[str]:
    """Append missing canonical keys to ``world.terrain_registry`` (R34).

    Mutates the world column in place — the caller owns the write
    (``worlds.update`` / ``world_repo.update``). Keys outside the
    canonical engine set are skipped (closed ``ReliefConditionTerrain``
    should always resolve). Logs ``r34_terrain_upsert`` per added key;
    returns the added keys.
    """
    entries = missing_terrain_entries(world, needed)
    raw_rows = list(world.terrain_registry or [])
    added: list[str] = []
    for entry in entries:
        key = entry.system_terrain
        raw_rows.append(entry.model_dump(mode="json"))
        added.append(key)
        relief_warning(
            "r34_terrain_upsert",
            world_uid=world.world_uid,
            system_terrain=key,
            source=source,
            template_uid=template_uid,
            system_name=system_name,
        )
    if added:
        world.terrain_registry = raw_rows
    return added
