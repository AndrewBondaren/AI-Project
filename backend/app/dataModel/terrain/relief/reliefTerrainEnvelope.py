"""Ontology envelope per ``ReliefConditionTerrain`` — tz_terrain_relief R37.

Engine floor: template knobs may be gentler, not steeper/shorter.
Not world JSON in v1 — ``canonical_defaults()`` is SoT.
"""

from __future__ import annotations

import math
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain, ReliefContext
from app.dataModel.terrain.relief.gradeLeftoverPair import (
    LEFTOVER_SHEER_MIN_DEG,
    theta_is_sheer,
)
from app.dataModel.terrain.relief.reliefSlopeGeom import (
    angle_from_height_length,
    length_from_target_angle,
)

_ANGLE_EPS_DEG = 1e-9
_SHEER_LENGTH_CELLS = 1

_OPEN_LAND_SLOPE_MIN_CELLS = 20
# Honest land SHEER floor [80, 90) — same number as leftover L=1 pair.
_OPEN_LAND_SLOPE_MAX_DEG = LEFTOVER_SHEER_MIN_DEG

_SHORE_SLOPE_MIN_DEG = 20.0
_SHORE_SLOPE_MAX_DEG = 70.0
_SHORE_CONTEXTS = (ReliefContext.SHORE,)


def _open_land_grade_floor(
    *,
    slope_preferred: bool,
    sheer_min_abs_dz: int,
    slope_max_angle_deg: float,
    stamp_min_abs_dz: int,
) -> ReliefTerrainEnvelope:
    """Shared plains/forest construction floor (R37). SHEER L is always 1.

    ``slope_length_min_cells`` applies when the ray is long enough. Fitness of a
    short ray is θ vs ``slope_max_angle_deg``, not L < L_min → SHEER.
    """
    return ReliefTerrainEnvelope(
        slope_max_angle_deg=slope_max_angle_deg,
        slope_length_min_cells=_OPEN_LAND_SLOPE_MIN_CELLS,
        sheer_allowed=True,
        slope_preferred=slope_preferred,
        allow_l_gt_h=True,
        sheer_min_abs_dz=sheer_min_abs_dz,
        stamp_min_abs_dz=stamp_min_abs_dz,
        apply_in_contexts=(ReliefContext.OPEN_LAND,),
    )


def _plains_canonical() -> ReliefTerrainEnvelope:
    """Plains: SLOPE θ < 80°; SHEER if the ray is steeper than the leftover floor."""
    return _open_land_grade_floor(
        slope_preferred=True,
        sheer_min_abs_dz=0,
        slope_max_angle_deg=_OPEN_LAND_SLOPE_MAX_DEG,
        stamp_min_abs_dz=1,
    )


def _forest_canonical() -> ReliefTerrainEnvelope:
    """Forest: same θ_max 80° as plains; SHEER still allowed when ``|dz| >= 4``."""
    return _open_land_grade_floor(
        slope_preferred=False,
        sheer_min_abs_dz=4,
        slope_max_angle_deg=_OPEN_LAND_SLOPE_MAX_DEG,
        stamp_min_abs_dz=2,
    )


def _shore_river_canonical() -> ReliefTerrainEnvelope:
    """Plains river: SLOPE/SHEER; L min 2; grade the channel bed."""
    return ReliefTerrainEnvelope(
        slope_length_min_cells=2,
        sheer_allowed=True,
        allow_l_gt_h=True,
        grades_channel_bed=True,
        apply_in_contexts=_SHORE_CONTEXTS,
    )


def _shore_mountain_river_canonical() -> ReliefTerrainEnvelope:
    """Mountain river: SLOPE θ in [20°, 70°]; L min 2; grade the channel bed."""
    return ReliefTerrainEnvelope(
        slope_min_angle_deg=_SHORE_SLOPE_MIN_DEG,
        slope_max_angle_deg=_SHORE_SLOPE_MAX_DEG,
        slope_length_min_cells=2,
        sheer_allowed=True,
        allow_l_gt_h=True,
        grades_channel_bed=True,
        apply_in_contexts=_SHORE_CONTEXTS,
    )


def _shore_lake_canonical() -> ReliefTerrainEnvelope:
    """Lake: same floor as plains river; own row — not ``shore_river``."""
    return ReliefTerrainEnvelope(
        slope_length_min_cells=2,
        sheer_allowed=True,
        allow_l_gt_h=True,
        grades_channel_bed=True,
        apply_in_contexts=_SHORE_CONTEXTS,
    )


def _shore_sea_canonical() -> ReliefTerrainEnvelope:
    """Sea: SLOPE θ in [20°, 70°]; L min 5; SHEER h≥5 or terraces L≥5."""
    return ReliefTerrainEnvelope(
        slope_min_angle_deg=_SHORE_SLOPE_MIN_DEG,
        slope_max_angle_deg=_SHORE_SLOPE_MAX_DEG,
        slope_length_min_cells=5,
        sheer_allowed=True,
        sheer_min_abs_dz=5,
        sheer_terrace_min_cells=5,
        allow_l_gt_h=True,
        apply_in_contexts=_SHORE_CONTEXTS,
    )


def _ravine_canonical() -> ReliefTerrainEnvelope:
    """Ravine: equal-z floor continues L (same walk flag as channel bed). Geom pass-through."""
    return ReliefTerrainEnvelope(grades_channel_bed=True)


class ReliefTerrainEnvelope(BaseModel):
    """Floor for one landcover class. All-omit = pass-through (no extra clamp)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    plateau_z_band_factor: DefaultOnWire[int] = constrained_field(
        default=0, greater_equals=0,
    )
    slope_max_angle_deg: DefaultOnWire[float | None] = None
    slope_min_angle_deg: DefaultOnWire[float | None] = None
    slope_length_min_cells: DefaultOnWire[int | None] = None
    slope_length_max_cells: DefaultOnWire[int | None] = None
    sheer_allowed: DefaultOnWire[bool] = True
    slope_preferred: DefaultOnWire[bool] = False
    allow_l_gt_h: DefaultOnWire[bool] = False
    sheer_min_abs_dz: DefaultOnWire[int] = constrained_field(
        default=0, greater_equals=0,
    )
    sheer_terrace_min_cells: DefaultOnWire[int | None] = None
    grades_channel_bed: DefaultOnWire[bool] = False
    stamp_min_abs_dz: DefaultOnWire[int] = constrained_field(
        default=1, greater_equals=1,
    )
    apply_in_contexts: DefaultOnWire[tuple[ReliefContext, ...] | None] = None

    @model_validator(mode="after")
    def _bounds(self) -> ReliefTerrainEnvelope:
        if (
            self.slope_length_min_cells is not None
            and self.slope_length_max_cells is not None
            and int(self.slope_length_min_cells) > int(self.slope_length_max_cells)
        ):
            raise ValueError(
                "slope_length_min_cells must be <= slope_length_max_cells"
            )
        if self.slope_max_angle_deg is not None:
            angle = float(self.slope_max_angle_deg)
            if angle <= 0.0 or angle >= 90.0:
                raise ValueError("slope_max_angle_deg must be in (0, 90)")
        if self.slope_min_angle_deg is not None:
            angle = float(self.slope_min_angle_deg)
            if angle <= 0.0 or angle >= 90.0:
                raise ValueError("slope_min_angle_deg must be in (0, 90)")
        if (
            self.slope_min_angle_deg is not None
            and self.slope_max_angle_deg is not None
            and float(self.slope_min_angle_deg) > float(self.slope_max_angle_deg)
        ):
            raise ValueError("slope_min_angle_deg must be <= slope_max_angle_deg")
        if self.sheer_terrace_min_cells is not None and int(self.sheer_terrace_min_cells) < 1:
            raise ValueError("sheer_terrace_min_cells must be >= 1")
        return self

    def is_unconstrained(self) -> bool:
        return (
            int(self.plateau_z_band_factor) <= 0
            and self.slope_max_angle_deg is None
            and self.slope_min_angle_deg is None
            and self.slope_length_min_cells is None
            and self.slope_length_max_cells is None
            and not self.slope_preferred
            and not self.allow_l_gt_h
            and int(self.sheer_min_abs_dz) <= 0
            and self.sheer_terrace_min_cells is None
        )

    def applies_to(self, context: ReliefContext) -> bool:
        if self.apply_in_contexts is None:
            return True
        return context in self.apply_in_contexts

    def plateau_abs_dz(self, z_band: int) -> int:
        return max(0, int(self.plateau_z_band_factor) * max(0, int(z_band)))

    @classmethod
    def canonical_sheer_length_cells(cls) -> int:
        """SHEER is always one XY column (R37)."""
        return _SHEER_LENGTH_CELLS

    def sheer_ok(self, h: int) -> bool:
        if not self.sheer_allowed:
            return False
        return int(h) >= int(self.sheer_min_abs_dz)

    def stamps_first_step(self, abs_dz: int, context: ReliefContext) -> bool:
        """Discover may propose this first-step |dz| (R37 / R41-T-7).

        Not a geom clamp: ``grade_constrained`` still classifies ``h=1`` as a
        gentle SLOPE when called without a seed. Pass-through contexts
        (``apply_in_contexts`` miss) do not inherit this floor.
        """
        if not self.applies_to(context):
            return True
        return int(abs_dz) >= int(self.stamp_min_abs_dz)

    def has_slope_length_constraints(self) -> bool:
        return (
            self.slope_max_angle_deg is not None
            or self.slope_min_angle_deg is not None
            or self.slope_length_min_cells is not None
            or self.slope_length_max_cells is not None
        )

    def length_from_min_cells(self) -> int:
        """Envelope L floor from ``slope_length_min_cells`` (omit → 1)."""
        if self.slope_length_min_cells:
            return int(self.slope_length_min_cells)
        return 1

    def length_from_max_angle(self, h: int) -> int | None:
        """Geom-B vs envelope ``θ_max``: ``L = ceil(h / tan θ_max)``."""
        if self.slope_max_angle_deg is None:
            return None
        h_i = max(0, int(h))
        if h_i < 1:
            return 1
        return length_from_target_angle(h_i, float(self.slope_max_angle_deg))

    def length_from_min_angle(self, h: int) -> int | None:
        """Max L so θ ≥ θ_min: ``L = floor(h / tan θ_min)``."""
        if self.slope_min_angle_deg is None:
            return None
        h_i = max(0, int(h))
        if h_i < 1:
            return 1
        tan_t = math.tan(math.radians(float(self.slope_min_angle_deg)))
        if tan_t <= 0.0:
            return None
        return max(1, math.floor(h_i / tan_t))

    def envelope_length_floor(self, h: int) -> int:
        """``max(L_min, ceil(h / tan θ_max))`` when constructing a long-ray ramp."""
        l_floor = self.length_from_min_cells()
        from_angle = self.length_from_max_angle(h)
        if from_angle is not None:
            l_floor = max(l_floor, from_angle)
        return l_floor

    def length_from_template(
        self,
        h: int,
        *,
        template_length: int | None = None,
        template_angle_deg: float | None = None,
        fallback: int,
    ) -> int:
        """Template XOR: Geom-B ``θ`` → L, else Geom-A L, else envelope floor."""
        h_i = max(0, int(h))
        if template_angle_deg is not None and h_i >= 1:
            try:
                return length_from_target_angle(h_i, float(template_angle_deg))
            except ValueError:
                return fallback
        if template_length is not None:
            return max(0, int(template_length))
        return fallback

    def clamp_slope_length(self, length: int) -> int:
        """Cap at ``slope_length_max_cells`` when set. Omit max = no cap."""
        out = max(0, int(length))
        if self.slope_length_max_cells is not None:
            out = min(out, int(self.slope_length_max_cells))
        return out

    def slope_walk_cap_cells(self) -> int | None:
        """Hard lockstep walk bound from ``slope_length_max_cells``. Omit = no envelope cap."""
        if self.slope_length_max_cells is None:
            return None
        return max(1, int(self.slope_length_max_cells))

    def slope_length_for(
        self,
        h: int,
        *,
        template_length: int | None = None,
        template_angle_deg: float | None = None,
        length_cap: int | None = None,
    ) -> int | None:
        """Construct L: ``min(max(L_template, L_floor including L_min), cap)``.

        ``None`` = keep template XOR. ``L_min`` is a construction floor here,
        not a ``slope_fits`` veto. Stamp call sites pass ``length_cap`` /
        ``path_length``; omit = classify/construct without a ray (plains
        ``dz=1`` may request L=20).
        """
        if not self.has_slope_length_constraints() and length_cap is None:
            return None
        if not self.has_slope_length_constraints():
            return max(0, int(length_cap)) if length_cap is not None else None
        l_floor = self.envelope_length_floor(h)
        l_tpl = self.length_from_template(
            h,
            template_length=template_length,
            template_angle_deg=template_angle_deg,
            fallback=l_floor,
        )
        length = self.clamp_slope_length(max(l_tpl, l_floor))
        l_ceil = self.length_from_min_angle(h)
        if l_ceil is not None:
            length = min(length, l_ceil)
        if length_cap is not None:
            length = min(length, max(0, int(length_cap)))
        return max(1, length)

    def slope_angle_deg(self, h: int, length: int) -> float:
        """Geom-A: ``θ = atan(h / L)`` for a candidate ramp."""
        return angle_from_height_length(h, length)

    def slope_fits(self, h: int, length: int) -> bool:
        """θ band only. ``slope_length_min_cells`` is a construction floor, not a veto."""
        h_i = max(0, int(h))
        l_i = int(length)
        if h_i < 1:
            return True
        if l_i < 1:
            return False
        theta = self.slope_angle_deg(h_i, l_i)
        if self.slope_max_angle_deg is not None:
            max_deg = float(self.slope_max_angle_deg)
            # Open-land θ_max is leftover SHEER floor: [max, 90) is not SLOPE.
            # Shore max is an inclusive SLOPE cap (archive R37).
            if math.isclose(max_deg, LEFTOVER_SHEER_MIN_DEG, abs_tol=_ANGLE_EPS_DEG):
                if theta_is_sheer(theta, floor_deg=max_deg):
                    return False
            elif theta > max_deg + _ANGLE_EPS_DEG:
                return False
        if self.slope_min_angle_deg is not None:
            if theta < float(self.slope_min_angle_deg) - _ANGLE_EPS_DEG:
                return False
        return True

    def slope_outcome(self, h: int, length: int) -> str:
        """``slope`` | ``sheer`` | ``skip`` after envelope length is known."""
        if self.slope_fits(h, length):
            return "slope"
        if self.sheer_ok(h):
            return "sheer"
        return "skip"

    def weights_for_fitted_slope(self, h: int) -> tuple[float, float] | None:
        """When SLOPE fits: ``(slope, sheer)`` override, or ``None`` to keep roll."""
        if self.slope_preferred or not self.sheer_ok(h):
            return (1.0, 0.0)
        return None


class ReliefOntologyEnvelopes(BaseModel):
    """Closed table keyed by ``ReliefConditionTerrain`` — tz_terrain_relief R37."""

    SCHEMA_ID: ClassVar[str] = "SCH-RELIEF-ONTOLOGY-ENVELOPES"

    model_config = ConfigDict(extra="ignore", frozen=True)

    plains: DefaultOnWire[ReliefTerrainEnvelope] = Field(
        default_factory=_plains_canonical,
    )
    forest: DefaultOnWire[ReliefTerrainEnvelope] = Field(
        default_factory=_forest_canonical,
    )
    mountain: DefaultOnWire[ReliefTerrainEnvelope] = Field(
        default_factory=ReliefTerrainEnvelope,
    )
    ravine: DefaultOnWire[ReliefTerrainEnvelope] = Field(
        default_factory=_ravine_canonical,
    )
    shore_river: DefaultOnWire[ReliefTerrainEnvelope] = Field(
        default_factory=_shore_river_canonical,
    )
    shore_mountain_river: DefaultOnWire[ReliefTerrainEnvelope] = Field(
        default_factory=_shore_mountain_river_canonical,
    )
    shore_lake: DefaultOnWire[ReliefTerrainEnvelope] = Field(
        default_factory=_shore_lake_canonical,
    )
    shore_sea: DefaultOnWire[ReliefTerrainEnvelope] = Field(
        default_factory=_shore_sea_canonical,
    )

    @classmethod
    def canonical_defaults(cls) -> ReliefOntologyEnvelopes:
        return cls()

    def for_terrain(
        self,
        terrain: ReliefConditionTerrain | str,
    ) -> ReliefTerrainEnvelope:
        key = terrain.value if isinstance(terrain, ReliefConditionTerrain) else terrain
        try:
            return getattr(self, key)
        except AttributeError:
            return ReliefTerrainEnvelope()
