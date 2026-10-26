"""N system_tiers → abstract bands — resolve wrapper over dataModel contract."""

from __future__ import annotations

from random import Random

from app.application.jsonValidation import economic_tiers
from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.generators.utils.tierRegistry import tier_rank, tiers_sorted
from app.dataModel.cascade.cascadeSpec import ChannelKind
from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.db.models.world import World


def tier_band_map(world: World) -> dict[str, str]:
    """Maps each system_tier → abstract band wire key (ASC base_value)."""
    tiers = tiers_sorted(economic_tiers(world).root)
    return EconomicTierBand.band_map_for_sorted_tiers(
        [tier.system_tier for tier in tiers],
    )


def band_of(world: World, system_tier: str) -> str | None:
    return tier_band_map(world).get(system_tier)


def tiers_for_band(world: World, band: str) -> list[str]:
    return EconomicTierBand.tiers_for_band_in_map(tier_band_map(world), band)


def materialize_tier_input(
    world:  World,
    kind:   ChannelKind,
    raw:    object,
    anchor: str | None,
    rng:    Random | None,
) -> str | None:
    """Cascade materialize entry (tz_cascade_context §4): resolves a
    BAND/RANGE authored input into one system_tier — nearest to the
    inherited ``anchor``, rng pick without it. ``None`` = the chain
    keeps walking."""
    if world is None:
        raise ValueError("economic_tier: materialize requires world")
    if kind is ChannelKind.BAND:
        if anchor is None and rng is None:
            raise ValueError(
                "economic_tier: band materialize without anchor "
                "requires rng"
            )
        return materialize_band(world, raw, rng, anchor_tier=anchor)
    if kind is ChannelKind.RANGE:
        return _materialize_tier_range(world, raw, anchor, rng)
    raise ValueError(f"economic_tier: unknown channel kind {kind}")


def _materialize_tier_range(world, raw, anchor, rng):
    """EconomicTierRange → tier: nearest to the inherited anchor inside
    ``[min, max]``; without anchor — rng pick (tz_cascade_context §4)."""
    registry = economic_tiers(world).root
    lo = tier_rank(registry, raw.min, world_uid=world.world_uid)
    hi = tier_rank(registry, raw.max, world_uid=world.world_uid)
    candidates = [
        entry.system_tier
        for index, entry in enumerate(tiers_sorted(registry))
        if lo <= index <= hi
    ]
    if not candidates:
        ctx = ResolveContext(path_prefix=("economic_tier",))
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, "no tiers satisfy authored band/range", code="DOMAIN_NO_CANDIDATE")])
    if anchor is None:
        if rng is None:
            raise ValueError(
                "economic_tier: range materialize without anchor "
                "requires rng"
            )
        return rng.choice(candidates)
    anchor_rank = tier_rank(registry, anchor, world_uid=world.world_uid)
    return min(
        candidates,
        key=lambda tier: abs(
            tier_rank(registry, tier, world_uid=world.world_uid)
            - anchor_rank
        ),
    )


def materialize_band(
    world:       World,
    band:        str,
    rng:         Random | None,
    anchor_tier: str | None = None,
) -> str | None:
    """
    Разворачивает economic_tier_band в один system_tier из registry мира.
    anchor_tier (обычно tier города) — предпочтение ближайшего тира в band.
    """
    if not isinstance(band, str) or EconomicTierBand.from_wire(band) is None:
        ctx = ResolveContext(path_prefix=("economic_tier_band",))
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, f"unknown economic tier band: {band!r}", code="DOMAIN_BAND")])
    registry = economic_tiers(world).root
    candidates = tiers_for_band(world, band)
    if not candidates:
        ctx = ResolveContext(path_prefix=("economic_tier",))
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, "no tiers satisfy authored band/range", code="DOMAIN_NO_CANDIDATE")])
    if anchor_tier is None:
        return rng.choice(candidates)

    anchor_rank = tier_rank(registry, anchor_tier, world_uid=world.world_uid)
    ordered = [
        tier.system_tier
        for tier in tiers_sorted(registry)
        if tier.system_tier in candidates
    ]
    if not ordered:
        return rng.choice(candidates)
    return min(
        ordered,
        key=lambda tier: abs(
            tier_rank(registry, tier, world_uid=world.world_uid) - anchor_rank
        ),
    )
