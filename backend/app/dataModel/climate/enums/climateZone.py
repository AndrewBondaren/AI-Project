"""Built-in climate zones — enum owns engine + wire-template profiles (SCH-WORLD-CLIMATE)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.dataModel.climate.climateZone.climateZoneEntry import ClimateZoneEntry


@dataclass(frozen=True)
class ClimateZoneProfileData:
    base_temperature: int
    typical_elevation_z: int
    base_rainfall: int
    temperature_variance: int
    rainfall_variance: int


@dataclass(frozen=True)
class _ClimateZoneBuiltin:
    """Engine profile; optional wire override for fixtures/world_template.json."""

    engine: ClimateZoneProfileData
    wire: ClimateZoneProfileData | None = None

    def select(self, *, wire: bool) -> ClimateZoneProfileData:
        if wire and self.wire is not None:
            return self.wire
        return self.engine


@dataclass(frozen=True)
class ClimateZoneProfile:
    """Resolved builtin profile — used by climate resolve layer."""

    system_climate: str
    base_temperature: int
    typical_elevation_z: int
    base_rainfall: int
    temperature_variance: int
    rainfall_variance: int

    @classmethod
    def from_data(cls, system_climate: str, data: ClimateZoneProfileData) -> ClimateZoneProfile:
        return cls(
            system_climate=system_climate,
            base_temperature=data.base_temperature,
            typical_elevation_z=data.typical_elevation_z,
            base_rainfall=data.base_rainfall,
            temperature_variance=data.temperature_variance,
            rainfall_variance=data.rainfall_variance,
        )


class ClimateZone(Enum):
    """Built-in climate zone keys. Custom zones exist only in world.climate_zone_registry."""

    ARCTIC = _ClimateZoneBuiltin(
        ClimateZoneProfileData(-25, 4, 20, 8, 10),
    )
    TUNDRA = _ClimateZoneBuiltin(
        ClimateZoneProfileData(-20, 3, 30, 10, 15),
    )
    SUBARCTIC = _ClimateZoneBuiltin(
        ClimateZoneProfileData(-15, 3, 25, 10, 12),
    )
    SUBPOLAR = _ClimateZoneBuiltin(
        ClimateZoneProfileData(-10, 2, 35, 10, 15),
    )
    COLD = _ClimateZoneBuiltin(
        ClimateZoneProfileData(-5, 2, 40, 8, 15),
        wire=ClimateZoneProfileData(-5, 8, 35, 10, 12),
    )
    COLD_TEMPERATE = _ClimateZoneBuiltin(
        ClimateZoneProfileData(0, 1, 45, 8, 18),
    )
    TEMPERATE = _ClimateZoneBuiltin(
        ClimateZoneProfileData(12, 0, 55, 8, 20),
        wire=ClimateZoneProfileData(12, 12, 50, 12, 15),
    )
    CONTINENTAL = _ClimateZoneBuiltin(
        ClimateZoneProfileData(8, 0, 45, 10, 18),
    )
    ARID = _ClimateZoneBuiltin(
        ClimateZoneProfileData(20, 0, 10, 12, 5),
    )
    MEDITERRANEAN = _ClimateZoneBuiltin(
        ClimateZoneProfileData(15, 0, 40, 8, 15),
    )
    SUBTROPICAL = _ClimateZoneBuiltin(
        ClimateZoneProfileData(22, -1, 65, 5, 15),
    )
    COASTAL = _ClimateZoneBuiltin(
        ClimateZoneProfileData(14, -1, 60, 6, 18),
    )
    MARITIME = _ClimateZoneBuiltin(
        ClimateZoneProfileData(12, -1, 70, 5, 20),
    )
    TROPICAL = _ClimateZoneBuiltin(
        ClimateZoneProfileData(28, -1, 80, 5, 15),
        wire=ClimateZoneProfileData(28, 6, 80, 6, 20),
    )
    DESERT = _ClimateZoneBuiltin(
        ClimateZoneProfileData(30, 0, 10, 12, 5),
        wire=ClimateZoneProfileData(32, 14, 8, 14, 5),
    )
    VOLCANIC = _ClimateZoneBuiltin(
        ClimateZoneProfileData(35, 2, 5, 10, 3),
    )
    WARM = _ClimateZoneBuiltin(
        ClimateZoneProfileData(22, 10, 45, 10, 12),
    )

    @property
    def system_climate(self) -> str:
        return self.name.lower()

    def __str__(self) -> str:
        return self.system_climate

    @classmethod
    def from_system_climate(cls, key: str) -> ClimateZone | None:
        norm = (key or "").strip().lower()
        for member in cls:
            if member.system_climate == norm:
                return member
        return None

    @classmethod
    def engine_members(cls) -> tuple[ClimateZone, ...]:
        return _ENGINE_MEMBERS

    @classmethod
    def wire_template_members(cls) -> tuple[ClimateZone, ...]:
        return _WIRE_TEMPLATE_MEMBERS

    def to_entry(self, *, wire: bool = False) -> ClimateZoneEntry:
        data = self.value.select(wire=wire)
        return ClimateZoneEntry(
            system_climate=self.system_climate,
            base_temperature=data.base_temperature,
            typical_elevation_z=data.typical_elevation_z,
            base_rainfall=data.base_rainfall,
            temperature_variance=data.temperature_variance,
            rainfall_variance=data.rainfall_variance,
        )

    def to_profile(self, *, wire: bool = False) -> ClimateZoneProfile:
        return ClimateZoneProfile.from_data(self.system_climate, self.value.select(wire=wire))

    def world_map_wire_id(self) -> int:
        """Stable L0 ``climate_zone_id`` — append-only table, not ``enumerate`` order."""
        return _WORLD_MAP_CLIMATE_ZONE_WIRE_ID[self.system_climate]

    @classmethod
    def from_world_map_wire_id(cls, wire_id: int) -> ClimateZone | None:
        key = _WORLD_MAP_CLIMATE_ZONE_BY_WIRE_ID.get(int(wire_id))
        if key is None:
            return None
        return cls.from_system_climate(key)


# Append-only: new zones get the next free id; never renumber existing keys.
_WORLD_MAP_CLIMATE_ZONE_WIRE_ID: dict[str, int] = {
    "arctic": 0,
    "tundra": 1,
    "subarctic": 2,
    "subpolar": 3,
    "cold": 4,
    "cold_temperate": 5,
    "temperate": 6,
    "continental": 7,
    "arid": 8,
    "mediterranean": 9,
    "subtropical": 10,
    "coastal": 11,
    "maritime": 12,
    "tropical": 13,
    "desert": 14,
    "volcanic": 15,
    "warm": 16,
}
_WORLD_MAP_CLIMATE_ZONE_BY_WIRE_ID: dict[int, str] = {
    v: k for k, v in _WORLD_MAP_CLIMATE_ZONE_WIRE_ID.items()
}

_ENGINE_MEMBERS: tuple[ClimateZone, ...] = (
    ClimateZone.ARCTIC,
    ClimateZone.TUNDRA,
    ClimateZone.SUBARCTIC,
    ClimateZone.SUBPOLAR,
    ClimateZone.COLD,
    ClimateZone.COLD_TEMPERATE,
    ClimateZone.TEMPERATE,
    ClimateZone.CONTINENTAL,
    ClimateZone.ARID,
    ClimateZone.MEDITERRANEAN,
    ClimateZone.SUBTROPICAL,
    ClimateZone.COASTAL,
    ClimateZone.MARITIME,
    ClimateZone.TROPICAL,
    ClimateZone.DESERT,
    ClimateZone.VOLCANIC,
)

_WIRE_TEMPLATE_MEMBERS: tuple[ClimateZone, ...] = (
    ClimateZone.ARCTIC,
    ClimateZone.COLD,
    ClimateZone.TEMPERATE,
    ClimateZone.WARM,
    ClimateZone.TROPICAL,
    ClimateZone.DESERT,
)
