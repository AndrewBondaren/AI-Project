"""
Вычисляет ширину тротуара (width_cells) из economic_tier скелета города.
Правила — см. tz_structure_connections.md §3.4; fallback по band — tz_economic_tier.md §10.
"""
import random

from app.application.worldData.generators.utils.economicTierBands import band_of
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
    Per-tier sidewalk_width_* on registry rows — future EconomyTierEntry fields;
    сейчас: band_of(world, tier) + EconomicTierBand defaults → DEFAULT_SIDEWALK_WIDTH_CELLS.
    """
    if economic_tier is None:
        return DEFAULT_SIDEWALK_WIDTH_CELLS

    if world is not None:
        band = band_of(world, economic_tier)
        if band is not None:
            width = sidewalk_width_for_band(band, rng)
            if width is not None:
                return width

    return DEFAULT_SIDEWALK_WIDTH_CELLS
