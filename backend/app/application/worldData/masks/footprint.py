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

    def __post_init__(self) -> None:
        if self.elevation_fraction:
            unknown = set(self.elevation_fraction) - set(self.cells)
            if unknown:
                raise ValueError(
                    f"MaskFootprint.elevation_fraction keys not in cells: {len(unknown)}"
                )
