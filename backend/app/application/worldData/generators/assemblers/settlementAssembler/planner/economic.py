"""Economic tier compatibility for district / building template selection."""

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.jsonValidation import economic_tiers
from app.application.worldData.generators.utils.tierRegistry import (
    tier_at_least,
    tier_at_most,
    tier_rank,
    tiers_within_rank_delta,
)
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.db.models.world import World


def check_district_economic_compat(
    template: DistrictTemplateEntry,
    skeleton: CitySkeleton,
    world:    World,
) -> bool:
    """Шаблон района совместим с economic_tier города."""
    city_tier = skeleton.economic_tier
    if not city_tier:
        return True

    registry = economic_tiers(world).root
    uid = world.world_uid
    tier_range = template.economic_tier_range
    if tier_range is None:
        return True
    if not tier_at_least(registry, city_tier, tier_range.min, world_uid=uid):
        return False
    if not tier_at_most(registry, city_tier, tier_range.max, world_uid=uid):
        return False
    return True


def building_tier_compatible(
    building_template: BuildingLayoutTemplate,
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

    registry = economic_tiers(world).root
    uid = world.world_uid
    allowed = tiers_within_rank_delta(registry, city_tier, delta, world_uid=uid)
    if not allowed:
        return True

    min_allowed = min(tier_rank(registry, t, world_uid=uid) for t in allowed)
    max_allowed = max(tier_rank(registry, t, world_uid=uid) for t in allowed)

    tier_range = building_template.economic_tier_range
    if tier_range is None:
        return True

    min_t = tier_range.min
    max_t = tier_range.max
    if tier_rank(registry, min_t, world_uid=uid) > max_allowed:
        return False
    if tier_rank(registry, max_t, world_uid=uid) < min_allowed:
        return False
    return True
