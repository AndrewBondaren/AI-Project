"""Wire street layout keys — tz_structure_connections.md."""

from __future__ import annotations

from enum import StrEnum


class StreetLayout(StrEnum):
    GRID = "grid"
    ORGANIC = "organic"
    RADIAL = "radial"
    CUL_DE_SAC = "cul_de_sac"
    COURTYARD = "courtyard"

    @classmethod
    def from_wire(
        cls,
        key: str | StreetLayout | None,
        *,
        default: StreetLayout | None = None,
    ) -> StreetLayout | None:
        if key is None:
            return default
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return default

    @classmethod
    def for_generator(cls, wire: str | None) -> StreetLayout:
        """Empty wire → GRID; unknown wire → ValueError (HY-5 roads)."""
        if wire is None or not str(wire).strip():
            return cls.GRID
        parsed = cls.from_wire(wire)
        if parsed is None:
            raise ValueError(f"Неизвестный street_layout: {wire!r}")
        return parsed

