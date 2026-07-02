import logging
from random import Random

from app.application.jsonValidation import economic_tiers, materials
from app.application.worldData.generators.utils.tierRegistry import median_system_tier, tiers_sorted
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.db.models.world import World

from app.dataModel.materials import (
    DEFAULT_FLOOR_MATERIAL,
    DEFAULT_WALL_MATERIAL,
)

logger = logging.getLogger(__name__)


def _construction_candidates(
    registry: list[MaterialRegistryEntry],
    use_type: str,
    tier: str,
) -> list[str]:
    return [
        entry.system_material
        for entry in registry
        if "construction" in entry.tags
        and use_type in entry.use_type
        and entry.economic_tier == tier
    ]


def resolve_material(
    world: World,
    use_type: str,
    effective_tier: str | None,
    rng: Random,
    default: str,
    context: str = "",
) -> str:
    """
    Выбирает материал из material_registry по use_type и economic_tier.
    Fallback: ближайший тир вниз → любой подходящий → default.
    """
    registry = materials(world).root
    tiers = tiers_sorted(economic_tiers(world).root)
    tier = effective_tier or median_system_tier(tiers) or ""

    found = _construction_candidates(registry, use_type, tier)

    if not found:
        current_val = next(
            (entry.base_value for entry in tiers if entry.system_tier == tier),
            0,
        )
        for tier_entry in reversed([entry for entry in tiers if entry.base_value < current_val]):
            found = _construction_candidates(registry, use_type, tier_entry.system_tier)
            if found:
                break

    if not found:
        found = [
            entry.system_material
            for entry in registry
            if "construction" in entry.tags
            and use_type in entry.use_type
        ]

    if not found:
        logger.warning("resolve_material: no %r material found%s, using default %r",
                       use_type, f" (room={context})" if context else "", default)
        return default

    return rng.choice(found)


def resolve_room_materials(
    world: World,
    room_tier: str | None,
    template_tier: str | None,
    rng: Random,
    room_id: str = "",
    building_tier: str | None = None,
    template: dict | None = None,
) -> tuple[str, str]:
    """Возвращает (wall_material, floor_material) для комнаты."""
    effective = TierResolver.resolve(
        world=world,
        room_tier=room_tier,
        template_tier=template_tier,
        building_tier=building_tier,
        building_band=TierResolver.band_from_template(template),
        rng=rng,
    )

    wall  = resolve_material(world, "wall",  effective, rng, DEFAULT_WALL_MATERIAL,  context=room_id)
    floor = resolve_material(world, "floor", effective, rng, DEFAULT_FLOOR_MATERIAL, context=room_id)
    return wall, floor
