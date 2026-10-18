"""R34 ``terrain_registry`` upsert — pack remap projection.

``tz_terrain_relief`` R34: bringing a relief template into a world may
upsert *missing* ``system_terrain`` keys from the canonical engine set —
existing rows are never overwritten. Single logic source for the relief
pack adapter (``instantiate_pack`` world-side remap, plan
``libpack-t2-relief-import-instantiate`` step 1).

Missing is judged on the **stored** rows, not the resolved POJO:
``resolve_registry_list_world`` auto-completes canonical entries on read
(T-29 overlay), so a resolved scan would never find a canonical key
absent — the raw-column scan mirrors the pointer mixin's convention.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

if TYPE_CHECKING:
    from app.db.models.world import World


def missing_terrain_entries(world: World, needed: Iterable[str]) -> list:
    """Pure R34 projection; emission and persistence belong to the caller."""
    have = {row.get("system_terrain") for row in world.terrain_registry or [] if isinstance(row, dict)}
    canon = {e.system_terrain: e for e in WorldTerrainRegistry.canonical_engine().root}
    return [canon[key] for key in sorted(set(needed)) if key not in have and key in canon]
