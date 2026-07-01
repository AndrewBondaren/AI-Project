"""Abstract economic tier bands — sidewalk width defaults (tz_economic_tier.md §3, tz_structure_connections.md §3.4)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class SidewalkWidthDefault:
    fixed: int | None = None
    width_range: tuple[int, int] | None = None

    def roll(self, rng: random.Random) -> int:
        if self.fixed is not None:
            return int(self.fixed)
        if self.width_range is not None:
            return rng.randint(int(self.width_range[0]), int(self.width_range[1]))
        raise ValueError("SidewalkWidthDefault has no fixed or range value")


@dataclass(frozen=True)
class _EconomicTierBandBuiltin:
    sidewalk_width: SidewalkWidthDefault


class EconomicTierBand(Enum):
    """Five-step band scale — independent of world's tier count."""

    POOR = _EconomicTierBandBuiltin(SidewalkWidthDefault(fixed=1))
    COMMON = _EconomicTierBandBuiltin(SidewalkWidthDefault(fixed=2))
    MIDDLE = _EconomicTierBandBuiltin(SidewalkWidthDefault(fixed=3))
    WEALTHY = _EconomicTierBandBuiltin(SidewalkWidthDefault(width_range=(4, 5)))
    RICH = _EconomicTierBandBuiltin(SidewalkWidthDefault(width_range=(6, 8)))

    @property
    def wire_value(self) -> str:
        return self.name.lower()

    def __str__(self) -> str:
        return self.wire_value

    @classmethod
    def from_wire(cls, key: str | None) -> EconomicTierBand | None:
        norm = (key or "").strip().lower()
        for member in cls:
            if member.wire_value == norm:
                return member
        return None

    def roll_sidewalk_width(self, rng: random.Random) -> int:
        return self.value.sidewalk_width.roll(rng)

    @classmethod
    def sidewalk_width_by_band(cls) -> dict[str, int | tuple[int, int]]:
        """Legacy map shape — fixed int or range tuple."""
        out: dict[str, int | tuple[int, int]] = {}
        for member in cls:
            spec = member.value.sidewalk_width
            if spec.fixed is not None:
                out[member.wire_value] = spec.fixed
            elif spec.width_range is not None:
                out[member.wire_value] = spec.width_range
        return out

    @classmethod
    def band_map_for_sorted_tiers(cls, system_tiers: list[str]) -> dict[str, str]:
        """
        Map N system_tiers (ASC by base_value) → band wire keys — tz_economic_tier.md §3.

        index 0 → poor; 1..median-1 → common; median → middle;
        median+1..n-2 → wealthy; n-1 → rich.
        N=1 → middle; N=2 → poor, rich.
        """
        n = len(system_tiers)
        if n == 0:
            return {}
        if n == 1:
            return {system_tiers[0]: cls.MIDDLE.wire_value}

        median = (n - 1) // 2
        result: dict[str, str] = {}
        for i, key in enumerate(system_tiers):
            if i == 0:
                result[key] = cls.POOR.wire_value
            elif i == n - 1:
                result[key] = cls.RICH.wire_value
            elif i == median:
                result[key] = cls.MIDDLE.wire_value
            elif i < median:
                result[key] = cls.COMMON.wire_value
            else:
                result[key] = cls.WEALTHY.wire_value
        return result

    @staticmethod
    def tiers_for_band_in_map(band_map: dict[str, str], band: str) -> list[str]:
        return [tier for tier, wire_band in band_map.items() if wire_band == band]


DEFAULT_SIDEWALK_WIDTH_CELLS = EconomicTierBand.COMMON.value.sidewalk_width.fixed or 2


def sidewalk_width_for_band(band: str, rng: random.Random) -> int | None:
    member = EconomicTierBand.from_wire(band)
    if member is None:
        return None
    return member.roll_sidewalk_width(rng)


# Wire-key aliases for tier_band_map consumers.
BAND_POOR = EconomicTierBand.POOR.wire_value
BAND_COMMON = EconomicTierBand.COMMON.wire_value
BAND_MIDDLE = EconomicTierBand.MIDDLE.wire_value
BAND_WEALTHY = EconomicTierBand.WEALTHY.wire_value
BAND_RICH = EconomicTierBand.RICH.wire_value
