"""Repair ``worlds`` row defaults via import ``normalize_world`` (not generator fallbacks).

When climate precipitation cannot resolve a liquid from the world registry,
re-run the same normalizer as create/import and persist. Generators must not
call this — orchestrators / ``WorldService`` only.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Any

from app.application.jsonValidation import (
    climate_scalars,
    default_precipitation_liquid,
    materials,
)
from app.application.jsonValidation.facade import normalize_world
from app.db.models.world import World

if TYPE_CHECKING:
    from app.db.repositories.iWorldRepository import IWorldRepository

logger = logging.getLogger(__name__)


class WorldClimateDefaultsError(RuntimeError):
    """World row lacks resolvable precipitation liquid after normalize repair."""


def world_row_as_wire(world: World) -> dict:
    return dataclasses.asdict(world)


def _prepare_wire_for_repair(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce empty registry blobs so facade merge materializes canonical defaults."""
    out = dict(data)
    if not out.get("material_registry"):
        out["material_registry"] = []
    # ``{}`` is present but not a list — adapter returns None and merge skips.
    zones = out.get("climate_zone_registry")
    if not zones or (isinstance(zones, dict) and not zones):
        out["climate_zone_registry"] = []
    return out


def apply_import_normalize_to_world(world: World) -> bool:
    """Mutate ``world`` in place with ``normalize_world`` defaults. Returns if changed."""
    before = world_row_as_wire(world)
    normalized = normalize_world(_prepare_wire_for_repair(before), partial=False)
    changed = False
    for key, value in normalized.items():
        if not hasattr(world, key):
            continue
        if getattr(world, key) != value:
            setattr(world, key, value)
            changed = True
    return changed


def precipitation_liquid_resolvable(world: World) -> bool:
    """True when ``materials(world)`` yields a usable liquid (incl. empty→canonical)."""
    registry = materials(world)
    key = climate_scalars(world).precipitation_liquid
    default_key = default_precipitation_liquid()
    entry = registry.entry_for(key)
    if entry is not None and entry.material_category.is_liquid():
        return True
    water = registry.entry_for(default_key)
    if water is not None and water.material_category.is_liquid():
        return True
    return any(m.material_category.is_liquid() for m in registry.root)


def world_climate_defaults_need_repair(world: World) -> bool:
    """Raw row gaps that should be rewritten via normalize (persist), not only read-healed."""
    raw_mats = getattr(world, "material_registry", None) or []
    if not raw_mats:
        return True
    if getattr(world, "precipitation_liquid", None) in (None, ""):
        return True
    if not any(
        isinstance(row, dict)
        and str(row.get("material_category", "")).lower() == "liquid"
        for row in raw_mats
        if isinstance(row, dict)
    ):
        # Non-empty registry with no liquid rows — corrupt relative to climate.
        return True
    return False


async def ensure_world_climate_defaults(
    world: World,
    *,
    repo: IWorldRepository | None = None,
) -> World:
    """If climate defaults are missing on the row, normalize + optional persist.

    ``repo`` None → in-memory repair only (caller must persist if needed).
    """
    if not world_climate_defaults_need_repair(world):
        return world

    logger.warning(
        "world climate defaults repair | world=%s reason=row_missing_climate_defaults",
        world.world_uid,
    )
    changed = apply_import_normalize_to_world(world)
    if changed and repo is not None:
        await repo.update(world)
        logger.info(
            "world climate defaults repaired and persisted | world=%s",
            world.world_uid,
        )
    elif changed:
        logger.info(
            "world climate defaults repaired in-memory (not persisted) | world=%s",
            world.world_uid,
        )

    if not precipitation_liquid_resolvable(world):
        raise WorldClimateDefaultsError(
            f"world={world.world_uid}: no liquid in material_registry after "
            "import normalize — restore world row (re-import / repair_defaults)",
        )
    return world
