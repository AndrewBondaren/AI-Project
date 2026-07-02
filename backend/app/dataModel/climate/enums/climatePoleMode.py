"""Wire `climate_pole_mode` keys — tz_climate.md § Pole."""

from __future__ import annotations

from enum import Enum

DEFAULT_CLIMATE_POLE_MODE = "autoresolve"


class ClimatePoleMode(Enum):
    MANUAL = "manual"
    AUTORESOLVE = "autoresolve"

    @property
    def wire_value(self) -> str:
        return self.value

    @classmethod
    def from_wire(cls, key: str | None) -> ClimatePoleMode:
        norm = (key or DEFAULT_CLIMATE_POLE_MODE).strip().lower()
        for member in cls:
            if member.wire_value == norm:
                return member
        return cls.AUTORESOLVE

    @classmethod
    def default(cls) -> ClimatePoleMode:
        return cls.AUTORESOLVE
