from app.application.worldData.generators.utils.tierRegistry import tiers_sorted
from app.db.models.world import World

BAND_POOR    = "poor"
BAND_COMMON  = "common"
BAND_MIDDLE  = "middle"
BAND_WEALTHY = "wealthy"
BAND_RICH    = "rich"


def tier_band_map(world: World) -> dict[str, str]:
    """
    Maps each system_tier → abstract band.

    Sorted by base_value ASC:
      index 0              → poor
      1 .. median-1        → common
      median ((n-1) // 2)  → middle
      median+1 .. n-2      → wealthy
      n-1                  → rich

    N=1: single tier → middle.
    N=2: index 0 → poor, index 1 → rich.
    """
    tiers = tiers_sorted(world.economic_tier_registry)
    n = len(tiers)
    if n == 0:
        return {}
    if n == 1:
        return {tiers[0]["system_tier"]: BAND_MIDDLE}

    median = (n - 1) // 2
    result: dict[str, str] = {}
    for i, t in enumerate(tiers):
        key = t["system_tier"]
        if i == 0:
            result[key] = BAND_POOR
        elif i == n - 1:
            result[key] = BAND_RICH
        elif i == median:
            result[key] = BAND_MIDDLE
        elif i < median:
            result[key] = BAND_COMMON
        else:
            result[key] = BAND_WEALTHY
    return result


def band_of(world: World, system_tier: str) -> str | None:
    """Returns the abstract band for a given system_tier, or None if not in registry."""
    return tier_band_map(world).get(system_tier)


def tiers_for_band(world: World, band: str) -> list[str]:
    """Returns all system_tier values that belong to the given abstract band."""
    return [k for k, v in tier_band_map(world).items() if v == band]
