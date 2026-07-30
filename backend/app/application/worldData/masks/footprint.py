"""Shared mask footprint types — tz_map_light_bake § MaskDomain materialize."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class LightCellRef:
    gx: int
    gy: int
    tx: int
    ty: int

    def as_absolute(self, side: int) -> tuple[int, int]:
        return self.gx * side + self.tx, self.gy * side + self.ty


@dataclass(frozen=True, slots=True)
class MaskFootprint:
    """Result of ``materialize(Spec)`` — typed payloads, not a free-form attr bag."""

    cells: frozenset[LightCellRef]
    elevation_fraction: Mapping[LightCellRef, float] = field(default_factory=dict)
    system_facing: Mapping[LightCellRef, str | None] = field(default_factory=dict)
    """Uphill cardinal per light cell (relief grade); None = SHEER / unset."""

    def __post_init__(self) -> None:
        if self.elevation_fraction:
            unknown = set(self.elevation_fraction) - set(self.cells)
            if unknown:
                raise ValueError(
                    f"MaskFootprint.elevation_fraction keys not in cells: {len(unknown)}"
                )
        if self.system_facing:
            unknown_f = set(self.system_facing) - set(self.cells)
            if unknown_f:
                raise ValueError(
                    f"MaskFootprint.system_facing keys not in cells: {len(unknown_f)}"
                )
