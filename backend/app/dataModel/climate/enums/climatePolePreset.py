"""Wire `climate_pole_preset` keys and autoresolve pole specs — tz_climate.md § Autoresolve."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.climate.worldClimateScalars import DEFAULT_CLIMATE_POLE_PRESET


@dataclass(frozen=True)
class ClimatePoleSpec:
    pole_kind: str
    system_climate_zone: str

    @classmethod
    def cold(cls, zone: ClimateZone) -> ClimatePoleSpec:
        return cls(pole_kind="cold", system_climate_zone=zone.system_climate)

    @classmethod
    def hot(cls, zone: ClimateZone) -> ClimatePoleSpec:
        return cls(pole_kind="hot", system_climate_zone=zone.system_climate)


@dataclass(frozen=True)
class _ClimatePolePresetBuiltin:
    specs: tuple[ClimatePoleSpec, ...]


class ClimatePolePreset(Enum):
    """Autoresolve pole layout when no manual ``climate_pole`` — tz_climate.md."""

    ICE = _ClimatePolePresetBuiltin((ClimatePoleSpec.cold(ClimateZone.ARCTIC),))
    DESERT = _ClimatePolePresetBuiltin((ClimatePoleSpec.hot(ClimateZone.DESERT),))
    BINARY = _ClimatePolePresetBuiltin(
        (
            ClimatePoleSpec.cold(ClimateZone.ARCTIC),
            ClimatePoleSpec.hot(ClimateZone.TROPICAL),
        ),
    )

    @property
    def wire_value(self) -> str:
        return self.name.lower()

    def pole_specs(self) -> tuple[ClimatePoleSpec, ...]:
        return self.value.specs

    @classmethod
    def from_wire(cls, key: str | None) -> ClimatePolePreset:
        norm = (key or DEFAULT_CLIMATE_POLE_PRESET).strip().lower()
        for member in cls:
            if member.wire_value == norm:
                return member
        return cls.BINARY


def pole_specs_for_preset(preset: str | None) -> tuple[ClimatePoleSpec, ...]:
    return ClimatePolePreset.from_wire(preset).pole_specs()
