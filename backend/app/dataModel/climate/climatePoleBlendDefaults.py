"""Inverse-distance pole field blend — tz_climate.md § Pole field."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClimatePoleBlendDefaults:
    eps: float = 1.0
    power: float = 1.5
    single_pole_fade_diagonal_factor: float = 0.5


CLIMATE_POLE_BLEND = ClimatePoleBlendDefaults()
