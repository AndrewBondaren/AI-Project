"""
Общий доступ к worlds.economic_tier_registry: сортировка и ordinal-сравнение.

Не заменяет:
  - TierResolver — каскад room → building → district → city
  - economicTierBands — нормализация N тиров в abstract bands (poor…rich)
  - materialResolver — выбор материала с fallback вниз по base_value
"""
from __future__ import annotations

from app.application.worldData.generators.climate.loggingHelpers import warn_once

Registry = list[dict]


def tiers_sorted(registry: Registry | None) -> list[dict]:
    return sorted(registry or [], key=lambda t: t.get("base_value", 0))


def tier_entry(registry: Registry | None, system_tier: str | None) -> dict | None:
    if not system_tier:
        return None
    for entry in registry or []:
        if entry.get("system_tier") == system_tier:
            return entry
    return None


def tier_rank(
    registry: Registry | None,
    system_tier: str | None,
    *,
    world_uid: str | None = None,
) -> int:
    """Порядковый индекс по base_value ASC; null → 0; unknown → warn + 0 (JV-7)."""
    if not system_tier:
        return 0
    for i, entry in enumerate(tiers_sorted(registry)):
        if entry.get("system_tier") == system_tier:
            return i
    if world_uid:
        warn_once(
            world_uid,
            f"unknown_tier:{system_tier}",
            "tier_rank | world=%s unknown system_tier=%r; treating as rank 0",
            system_tier,
        )
    return 0


def tier_at_least(
    registry: Registry | None,
    actual: str | None,
    minimum: str | None,
    *,
    world_uid: str | None = None,
) -> bool:
    if minimum is None:
        return True
    return tier_rank(registry, actual, world_uid=world_uid) >= tier_rank(
        registry, minimum, world_uid=world_uid,
    )


def tier_at_most(
    registry: Registry | None,
    actual: str | None,
    maximum: str | None,
    *,
    world_uid: str | None = None,
) -> bool:
    if maximum is None:
        return True
    return tier_rank(registry, actual, world_uid=world_uid) <= tier_rank(
        registry, maximum, world_uid=world_uid,
    )


def median_system_tier(registry: Registry | None) -> str | None:
    tiers = tiers_sorted(registry)
    if not tiers:
        return None
    return tiers[len(tiers) // 2].get("system_tier")


def tiers_within_rank_delta(
    registry: Registry | None,
    center:   str | None,
    delta:    int = 1,
    *,
    world_uid: str | None = None,
) -> list[str]:
    """system_tier в пределах ±delta rank от center (для ±1 совместимости district/building)."""
    if not center:
        return []
    center_rank = tier_rank(registry, center, world_uid=world_uid)
    return [
        entry["system_tier"]
        for i, entry in enumerate(tiers_sorted(registry))
        if abs(i - center_rank) <= delta
    ]
