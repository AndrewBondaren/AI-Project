"""Runtime-only schedule after normalize (I8) — not wire JSON."""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.terrain.relief.reliefGradeKnobs import ReliefGradeKnobs

_DEFAULT_WIDTH = int(ReliefGradeKnobs.model_fields["shoulder_width_cells"].default)


@dataclass(frozen=True, slots=True)
class ReliefDeltaInterval:
    """Inclusive value range along |dz| or signed direction axis."""

    value_min: int
    value_max: int | None  # None = unbounded
    slope_weight: float
    sheer_weight: float
    shoulder_width_cells: int = _DEFAULT_WIDTH
    earthen_canal: bool = False
    structure_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReliefDeltaSchedule:
    """Normalized condition — consumers classify against this only."""

    none_max_abs: int
    none_knobs: ReliefDeltaInterval | None
    down: tuple[ReliefDeltaInterval, ...]
    up: tuple[ReliefDeltaInterval, ...]
