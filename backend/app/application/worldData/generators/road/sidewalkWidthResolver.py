"""
Вычисляет ширину тротуара (width_cells) из economic_tier скелета города.
Правила — см. tz_structure_connections.md §3.4; fallback по band — tz_economic_tier.md §10.
"""
import random

from app.application.worldData.generators.masterData import economic_tier_rows
from app.application.worldData.generators.utils.economicTierBands import band_of
from app.application.worldData.generators.utils.tierRegistry import tier_entry
from app.dataModel.economy.enums.economicTierBand import (
    DEFAULT_SIDEWALK_WIDTH_CELLS,
    sidewalk_width_for_band,
)
from app.db.models.world import World


def resolve_sidewalk_width(
    economic_tier: str | None,
    rng:           random.Random,
    world:         World | None = None,
) -> int:
    """
    Возвращает ширину тротуара в клетках.
    Приоритет: economic_tier_registry.sidewalk_width_cells / sidewalk_width_range
    → band_of(world, tier) + EconomicTierBand defaults → DEFAULT_SIDEWALK_WIDTH_CELLS.
    """
    if economic_tier is None:
        return DEFAULT_SIDEWALK_WIDTH_CELLS

    registry = economic_tier_rows(world) if world else None
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
            width = sidewalk_width_for_band(band, rng)
            if width is not None:
                return width

    return DEFAULT_SIDEWALK_WIDTH_CELLS
