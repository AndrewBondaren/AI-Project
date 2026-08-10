"""One slope policy case — Mode A (delta_z) or Mode B (bands) — tz_terrain_relief R32/R36b.

Mode A knobs: flat wire (T-34A); validate / read via ``ReliefGradeKnobs`` compose.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire
from app.dataModel.terrain.relief.enums import ReliefSlopePolicy
from app.dataModel.terrain.relief.reliefDeltaBand import ReliefDeltaBand
from app.dataModel.terrain.relief.reliefGradeKnobs import (
    ReliefGradeKnobs,
    reject_removed_shoulder_width,
    resolved_slope_length_cells,
    validate_canal_flat_refs,
    validate_canal_xor,
)

# Overlap check: unbounded max acts as a blocker for any later band
UNBOUNDED_DELTA_Z_MAX = 10**9


class ReliefRoleCase(BaseModel):
    """Exactly one of Mode A (delta_z + knobs) or Mode B (bands); not both."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    policy: StrictEnumOnWire[ReliefSlopePolicy]
    # Mode A threshold + flat knobs (wire); knobs SoT = ``mode_a_grade_knobs()``
    delta_z: DefaultOnWire[int | None] = None
    slope_weight: DefaultOnWire[float | None] = None
    sheer_weight: DefaultOnWire[float | None] = None
    slope_length_cells: DefaultOnWire[int | None] = None
    target_angle_deg: DefaultOnWire[float | None] = None
    earthen_canal: DefaultOnWire[bool | None] = None
    structure_canal: DefaultOnWire[str | None] = None
    structure_refs: DefaultOnWire[list[str]] = Field(default_factory=list)
    # Mode B
    bands: DefaultOnWire[list[ReliefDeltaBand] | None] = None

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy_width(cls, data: Any) -> Any:
        return reject_removed_shoulder_width(data)

    @model_validator(mode="after")
    def _xor_mode(self) -> ReliefRoleCase:
        has_delta = self.delta_z is not None
        has_bands = self.bands is not None
        if has_delta and has_bands:
            raise ValueError("ReliefRoleCase: cannot mix delta_z and bands (R32)")
        if not has_delta and not has_bands:
            raise ValueError("ReliefRoleCase: need delta_z (Mode A) or bands (Mode B)")

        if has_delta:
            dz = int(self.delta_z)  # type: ignore[arg-type]
            if self.policy == ReliefSlopePolicy.SLOPE_NONE:
                if dz < 0:
                    raise ValueError("slope_none delta_z must be >= 0")
            elif dz < 1:
                raise ValueError(f"{self.policy.value} delta_z must be >= 1")
            # Weights / geom / canal — single SoT (RELIEF-T-34A)
            self.mode_a_grade_knobs()
        else:
            assert self.bands is not None
            if self.policy == ReliefSlopePolicy.SLOPE_NONE:
                if len(self.bands) != 0:
                    raise ValueError("slope_none Mode B requires bands: []")
            elif len(self.bands) < 1:
                raise ValueError(f"{self.policy.value} Mode B requires non-empty bands")
            _reject_band_overlap(self.bands)
            # Case-level canal attachments (bands carry their own knobs)
            validate_canal_xor(self.earthen_canal, self.structure_canal)
            validate_canal_flat_refs(self.structure_canal, self.structure_refs)
        return self

    @property
    def is_mode_a(self) -> bool:
        return self.delta_z is not None

    def mode_a_grade_knobs(self) -> ReliefGradeKnobs:
        """Compose Mode A flat fields into ``ReliefGradeKnobs`` (validate + typed read)."""
        if not self.is_mode_a:
            raise RuntimeError("mode_a_grade_knobs is only valid for Mode A cases")
        payload = {
            name: getattr(self, name)
            for name in ReliefGradeKnobs.model_fields
        }
        try:
            return ReliefGradeKnobs.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def outward_length_cells(self) -> int:
        if self.is_mode_a:
            return self.mode_a_grade_knobs().outward_length_cells()
        return resolved_slope_length_cells(self.slope_length_cells)


def _reject_band_overlap(bands: list[ReliefDeltaBand]) -> None:
    """Inclusive intervals must not overlap (R32)."""
    ordered = sorted(
        bands,
        key=lambda b: (b.delta_z_min, b.delta_z_max is None, b.delta_z_max or 0),
    )
    prev_max: int | None = None
    for band in ordered:
        if prev_max is not None and band.delta_z_min <= prev_max:
            raise ValueError(
                f"overlapping bands: delta_z_min={band.delta_z_min} "
                f"overlaps previous max={prev_max}"
            )
        if band.delta_z_max is None:
            prev_max = UNBOUNDED_DELTA_Z_MAX
        else:
            prev_max = band.delta_z_max
