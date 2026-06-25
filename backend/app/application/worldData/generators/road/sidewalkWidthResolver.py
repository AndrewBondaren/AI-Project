"""
Вычисляет ширину тротуара (width_cells) из economic_tier города.
Правила — см. tz_structure_connections.md §3.4 (Sidewalk).
"""
import random

# economic_tier → ширина тротуара; диапазон (min, max) выбирается rng
_SIDEWALK_WIDTH: dict[str, int | tuple[int, int]] = {
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
) -> int:
    """
    Возвращает ширину тротуара в клетках.
    Если economic_tier не задан — возвращает дефолтную ширину (basic=2).
    Диапазонные значения (premium, exceptional) выбираются случайно через rng.
    """
    if economic_tier is None:
        return _DEFAULT_WIDTH

    spec = _SIDEWALK_WIDTH.get(economic_tier, _DEFAULT_WIDTH)
    if isinstance(spec, tuple):
        return rng.randint(spec[0], spec[1])
    return spec
