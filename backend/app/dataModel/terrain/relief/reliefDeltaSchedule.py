"""Runtime-only schedule after normalize (I8) — not wire JSON."""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.terrain.relief.reliefGradeKnobs import (
    DEFAULT_SLOPE_LENGTH_CELLS,
    resolved_slope_length_cells,
)


@dataclass(frozen=True, slots=True)
class ReliefDeltaInterval:
    """Inclusive value range along |dz| or signed direction axis."""

    value_min: int
    value_max: int | None  # None = unbounded
    slope_weight: float
    sheer_weight: float
    slope_length_cells: int | None = None
    target_angle_deg: float | None = None
    earthen_canal: bool | None = None
    structure_canal: str | None = None
    structure_refs: tuple[str, ...] = ()

    def outward_length_cells(self) -> int:
        return resolved_slope_length_cells(
            self.slope_length_cells,
            default=DEFAULT_SLOPE_LENGTH_CELLS,
        )


@dataclass(frozen=True, slots=True)
class ReliefDeltaSchedule:
    """Normalized condition — consumers classify against this only."""

    none_max_abs: int
    none_knobs: ReliefDeltaInterval | None
    down: tuple[ReliefDeltaInterval, ...]
    up: tuple[ReliefDeltaInterval, ...]
