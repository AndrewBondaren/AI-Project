"""Economic tier compatibility for district / building template selection."""

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.utils.economicTierBands import band_of
from app.application.worldData.generators.utils.tierRegistry import (
    tier_at_least,
    tier_at_most,
    tier_rank,
    tiers_within_rank_delta,
)
from app.db.models.world import World


def check_district_economic_compat(
    template: dict,
    skeleton: CitySkeleton,
    world:    World,
) -> bool:
    """Шаблон района совместим с economic_tier / band города."""
    city_tier = skeleton.economic_tier
    if not city_tier:
        return True

    registry = world.economic_tier_registry
    uid = world.world_uid
    tier_range = template.get("economic_tier_range")
    if tier_range:
        min_t = tier_range.get("min")
        max_t = tier_range.get("max")
        if min_t and not tier_at_least(registry, city_tier, min_t, world_uid=uid):
            return False
        if max_t and not tier_at_most(registry, city_tier, max_t, world_uid=uid):
            return False

    band = template.get("economic_tier_band")
    if band:
        city_band = band_of(world, city_tier)
        if city_band != band:
            return False

    return True


def building_tier_compatible(
    building_template: dict,
    city_skeleton:     CitySkeleton,
    world:             World,
    delta:             int = 1,
) -> bool:
    """
    building_template.economic_tier_range пересекается с city ± delta тир.
    v1 фильтр для plan_area_placements / buildingCache.collect_building_template_names.
    """
    city_tier = city_skeleton.economic_tier
    if not city_tier:
        return True

    registry = world.economic_tier_registry
    uid = world.world_uid
    allowed = tiers_within_rank_delta(registry, city_tier, delta, world_uid=uid)
    if not allowed:
        return True

    min_allowed = min(tier_rank(registry, t, world_uid=uid) for t in allowed)
    max_allowed = max(tier_rank(registry, t, world_uid=uid) for t in allowed)

    tier_range = building_template.get("economic_tier_range") or {}
    min_t = tier_range.get("min")
    max_t = tier_range.get("max")
    if not min_t and not max_t:
        return True

    if min_t and tier_rank(registry, min_t, world_uid=uid) > max_allowed:
        return False
    if max_t and tier_rank(registry, max_t, world_uid=uid) < min_allowed:
        return False
    return True
