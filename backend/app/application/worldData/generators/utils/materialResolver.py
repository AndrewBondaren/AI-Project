import logging
from random import Random

from app.application.jsonValidation import economic_tier_rows, material_rows
from app.application.worldData.generators.utils.tierRegistry import (
    median_system_tier,
    tiers_sorted,
)
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.db.models.world import World

from app.dataModel.materials import (
    DEFAULT_FLOOR_MATERIAL,
    DEFAULT_WALL_MATERIAL,
)

logger = logging.getLogger(__name__)


def resolve_material(
    world: World,
    use_type: str,
    effective_tier: str | None,
    rng: Random,
    default: str,
    context: str = "",
) -> str:
    """
    Выбирает материал из world.material_registry по use_type и economic_tier.
    Fallback: ближайший тир вниз → любой подходящий → default.
    """
    registry = material_rows(world)
    tiers = tiers_sorted(economic_tier_rows(world))
    tier = effective_tier or median_system_tier(economic_tier_rows(world)) or ""

    def candidates_for(t: str) -> list[str]:
        return [
            m["system_material"] for m in registry
            if "construction" in m.get("tags", [])
            and use_type in m.get("use_type", [])
            and m.get("economic_tier") == t
        ]

    found = candidates_for(tier)

    if not found:
        current_val = next(
            (t.get("base_value", 0) for t in tiers if t.get("system_tier") == tier), 0
        )
        for t_entry in reversed([t for t in tiers if t.get("base_value", 0) < current_val]):
            found = candidates_for(t_entry["system_tier"])
            if found:
                break

    if not found:
        found = [
            m["system_material"] for m in registry
            if "construction" in m.get("tags", [])
            and use_type in m.get("use_type", [])
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
