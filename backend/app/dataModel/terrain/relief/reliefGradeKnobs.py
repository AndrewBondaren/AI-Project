"""Shared grade knobs (weights / geom L|θ / attachments) — tz_terrain_relief R22/R27/R28/R36b."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field

WEIGHT_SUM_EPS = 1e-6
DEFAULT_SLOPE_LENGTH_CELLS = 1
_REMOVED_SHOULDER_WIDTH = "shoulder_width_cells"


def weights_sum_ok(slope_weight: float, sheer_weight: float) -> bool:
    return abs(float(slope_weight) + float(sheer_weight) - 1.0) <= WEIGHT_SUM_EPS


def reject_removed_shoulder_width(data: Any) -> Any:
    """``shoulder_width_cells`` removed — use ``slope_length_cells`` (R36b)."""
    if isinstance(data, dict) and _REMOVED_SHOULDER_WIDTH in data:
        raise ValueError(
            "shoulder_width_cells removed; use slope_length_cells (R36b)"
        )
    return data


def validate_geom_xor(
    slope_length_cells: int | None,
    target_angle_deg: float | None,
) -> None:
    """Exactly one geom knob, or neither (→ default L). Both → reject (R36b)."""
    has_l = slope_length_cells is not None
    has_a = target_angle_deg is not None
    if has_l and has_a:
        raise ValueError(
            "slope_length_cells XOR target_angle_deg — both set (R36b)"
        )
    if has_l and int(slope_length_cells) < 0:  # type: ignore[arg-type]
        raise ValueError("slope_length_cells must be >= 0")
    if has_a:
        angle = float(target_angle_deg)  # type: ignore[arg-type]
        if angle <= 0.0 or angle >= 90.0:
            raise ValueError("target_angle_deg must be in (0, 90) for SLOPE geom")


def validate_canal_xor(
    earthen_canal: bool | None,
    structure_canal: str | None,
) -> None:
    """``earthen_canal: true`` XOR ``structure_canal`` ref (R28/R36q).

    Omit / ``False`` = no earthen; only explicit ``True`` conflicts with ref.
    """
    ref = (structure_canal or "").strip() or None
    if earthen_canal is True and ref is not None:
        raise ValueError(
            "earthen_canal XOR structure_canal — both set (R28/R36q)"
        )


def validate_canal_flat_refs(
    structure_canal: str | None,
    structure_refs: list[str] | tuple[str, ...] | None,
) -> None:
    """Flat ``structure_refs`` with ``structure_canal`` — not canonical (R28)."""
    ref = (structure_canal or "").strip() or None
    if ref and structure_refs:
        raise ValueError(
            "structure_refs with structure_canal — materials come from "
            "canal_template_registry (R28)"
        )


def resolved_slope_length_cells(
    slope_length_cells: int | None,
    *,
    default: int = DEFAULT_SLOPE_LENGTH_CELLS,
) -> int:
    """L for expand until geomResolve; angle-only / omit → default."""
    if slope_length_cells is not None:
        return int(slope_length_cells)
    return int(default)


class ReliefGradeKnobs(BaseModel):
    """Weights + Geom XOR L|θ + attachments — on Mode A case or Mode B band."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    slope_weight: StrictOnWire[float] = constrained_field(
        greater_equals=0.0, lesser_equals=1.0,
    )
    sheer_weight: StrictOnWire[float] = constrained_field(
        greater_equals=0.0, lesser_equals=1.0,
    )
    # R36b Geom XOR — neither → default L at resolve time
    slope_length_cells: DefaultOnWire[int | None] = None
    target_angle_deg: DefaultOnWire[float | None] = None
    earthen_canal: DefaultOnWire[bool | None] = None
    structure_canal: DefaultOnWire[str | None] = None
    structure_refs: DefaultOnWire[list[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy_width(cls, data: Any) -> Any:
        return reject_removed_shoulder_width(data)

    @model_validator(mode="after")
    def _weights_and_geom(self) -> ReliefGradeKnobs:
        if not weights_sum_ok(self.slope_weight, self.sheer_weight):
            raise ValueError(
                f"slope_weight + sheer_weight must == 1 (±{WEIGHT_SUM_EPS}); "
                f"got {self.slope_weight}+{self.sheer_weight}"
            )
        validate_geom_xor(self.slope_length_cells, self.target_angle_deg)
        validate_canal_xor(self.earthen_canal, self.structure_canal)
        validate_canal_flat_refs(self.structure_canal, self.structure_refs)
        return self

    def outward_length_cells(self) -> int:
        """Expand width when ``h`` unknown; Geom-B needs ``geom_resolve(h=…)``."""
        return resolved_slope_length_cells(self.slope_length_cells)
