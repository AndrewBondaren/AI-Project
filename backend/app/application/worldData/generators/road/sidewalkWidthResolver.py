"""
Вычисляет ширину тротуара (width_cells) из economic_tier скелета города.
Правила — см. tz_structure_connections.md §3.4; fallback по band — tz_economic_tier.md §10.
"""
import random

from app.application.worldData.generators.utils.economicTierBands import (
    BAND_COMMON,
    BAND_MIDDLE,
    BAND_POOR,
    BAND_RICH,
    BAND_WEALTHY,
    band_of,
)
from app.application.worldData.generators.utils.tierRegistry import tier_entry
from app.db.models.world import World

# fallback если в economic_tier_registry нет sidewalk_width_*
_BAND_SIDEWALK_WIDTH: dict[str, int | tuple[int, int]] = {
    BAND_POOR:    1,
    BAND_COMMON:  2,
    BAND_MIDDLE:  3,
    BAND_WEALTHY: (4, 5),
    BAND_RICH:    (6, 8),
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
    → band_of(world, tier) + _BAND_SIDEWALK_WIDTH → 2.
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

    if world is not None:
        band = band_of(world, economic_tier)
        if band is not None:
            spec = _BAND_SIDEWALK_WIDTH.get(band, _DEFAULT_WIDTH)
            if isinstance(spec, tuple):
                return rng.randint(spec[0], spec[1])
            return int(spec)

    return _DEFAULT_WIDTH
