"""N system_tiers → abstract bands — resolve wrapper over dataModel contract."""

from __future__ import annotations

from random import Random

from app.application.jsonValidation import economic_tier_rows
from app.application.worldData.generators.utils.tierRegistry import tier_rank, tiers_sorted
from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.db.models.world import World


def tier_band_map(world: World) -> dict[str, str]:
    """Maps each system_tier → abstract band wire key (ASC base_value)."""
    tiers = tiers_sorted(economic_tier_rows(world))
    return EconomicTierBand.band_map_for_sorted_tiers(
        [t["system_tier"] for t in tiers],
    )


def band_of(world: World, system_tier: str) -> str | None:
    return tier_band_map(world).get(system_tier)


def tiers_for_band(world: World, band: str) -> list[str]:
    return EconomicTierBand.tiers_for_band_in_map(tier_band_map(world), band)


def materialize_band(
    world:       World,
    band:        str,
    rng:         Random,
    anchor_tier: str | None = None,
) -> str | None:
    """
    Разворачивает economic_tier_band в один system_tier из registry мира.
    anchor_tier (обычно tier города) — предпочтение ближайшего тира в band.
    """
    candidates = tiers_for_band(world, band)
    if not candidates:
        return None
    if anchor_tier is None:
        return rng.choice(candidates)

    anchor_rank = tier_rank(economic_tier_rows(world), anchor_tier, world_uid=world.world_uid)
    ordered = [
        t["system_tier"]
        for t in tiers_sorted(economic_tier_rows(world))
        if t["system_tier"] in candidates
    ]
    if not ordered:
        return rng.choice(candidates)
    return min(
        ordered,
        key=lambda t: abs(
            tier_rank(economic_tier_rows(world), t, world_uid=world.world_uid) - anchor_rank
        ),
    )
