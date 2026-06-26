"""
Вычисляет ширину тротуара (width_cells) из economic_tier города.
Правила — см. tz_structure_connections.md §3.4 (Sidewalk).
"""
import random

from app.application.worldData.generators.utils.tierRegistry import tier_entry
from app.db.models.world import World

# fallback если в economic_tier_registry нет sidewalk_width_*
_DEFAULT_SIDEWALK_WIDTH: dict[str, int | tuple[int, int]] = {
    "poor":        1,
    "basic":       2,
    "standard":    3,
    "premium":     (4, 5),
    "exceptional": (6, 8),
}
_DEFAULT_WIDTH = 2


def resolve_sidewalk_width(
    economic_tier: str | None,
    rng:           random.Random,
    world:         World | None = None,
) -> int:
    """
    Возвращает ширину тротуара в клетках.
    Приоритет: economic_tier_registry.sidewalk_width_cells / sidewalk_width_range
    → встроенные дефолты по system_tier → 2.
    """
    if economic_tier is None:
        return _DEFAULT_WIDTH

    registry = world.economic_tier_registry if world else None
    entry = tier_entry(registry, economic_tier)
    if entry is not None:
        fixed = entry.get("sidewalk_width_cells")
        if fixed is not None:
            return int(fixed)
        width_range = entry.get("sidewalk_width_range")
        if isinstance(width_range, (list, tuple)) and len(width_range) >= 2:
            return rng.randint(int(width_range[0]), int(width_range[1]))

    spec = _DEFAULT_SIDEWALK_WIDTH.get(economic_tier, _DEFAULT_WIDTH)
    if isinstance(spec, tuple):
        return rng.randint(spec[0], spec[1])
    return int(spec)
