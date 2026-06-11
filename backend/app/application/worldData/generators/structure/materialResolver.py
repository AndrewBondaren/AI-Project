import logging
from random import Random

from app.db.models.world import World

logger = logging.getLogger(__name__)

_DEFAULT_WALL_MATERIAL  = "stone"
_DEFAULT_FLOOR_MATERIAL = "wood"


def _tiers_sorted(world: World) -> list[dict]:
    registry = world.economic_tier_registry or []
    return sorted(registry, key=lambda t: t.get("base_value", 0))


def _median_tier(tiers: list[dict]) -> str | None:
    if not tiers:
        return None
    return tiers[len(tiers) // 2].get("system_tier")


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
    registry = world.material_registry or []
    tiers = _tiers_sorted(world)
    tier = effective_tier or _median_tier(tiers) or ""

    def candidates_for(t: str) -> list[str]:
        return [
            m["system_material"] for m in registry
            if "construction" in m.get("tags", [])
            and use_type in m.get("use_type", [])
            and m.get("economic_tier") == t
        ]

    found = candidates_for(tier)

    if not found:
        # fallback вниз по base_value
        current_val = next(
            (t.get("base_value", 0) for t in tiers if t.get("system_tier") == tier), 0
        )
        for t_entry in reversed([t for t in tiers if t.get("base_value", 0) < current_val]):
            found = candidates_for(t_entry["system_tier"])
            if found:
                break

    if not found:
        # любой подходящий, без фильтра по тиру
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
) -> tuple[str, str]:
    """Возвращает (wall_material, floor_material) для комнаты."""
    tiers = _tiers_sorted(world)
    effective = room_tier or template_tier or building_tier or _median_tier(tiers)

    wall  = resolve_material(world, "wall",  effective, rng, _DEFAULT_WALL_MATERIAL,  context=room_id)
    floor = resolve_material(world, "floor", effective, rng, _DEFAULT_FLOOR_MATERIAL, context=room_id)
    return wall, floor
