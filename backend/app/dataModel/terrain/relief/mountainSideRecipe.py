"""Mountain side_recipe — tz_terrain_relief R33."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.terrain.relief.enums import MountainSideRecipeMode, ReliefSideKind
from app.dataModel.terrain.relief.reliefGradeKnobs import WEIGHT_SUM_EPS, weights_sum_ok


class MountainSideRecipe(BaseModel):
    """XOR: weights | pattern | fixed kind; all empty → Mode D (seeded random)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    # Mode D (empty recipe) seeded weights — SoT for materialize (RELIEF-T-8)
    EMPTY_SLOPE_WEIGHT: ClassVar[float] = 0.5
    EMPTY_SHEER_WEIGHT: ClassVar[float] = 0.5

    slope_weight: DefaultOnWire[float | None] = None
    sheer_weight: DefaultOnWire[float | None] = None
    side_kinds: DefaultOnWire[list[ReliefSideKind] | None] = None
    default_side_kind: DefaultOnWire[ReliefSideKind | None] = None

    @model_validator(mode="after")
    def _xor_modes(self) -> MountainSideRecipe:
        has_weights = self.slope_weight is not None or self.sheer_weight is not None
        has_pattern = self.side_kinds is not None and len(self.side_kinds) > 0
        has_fixed = self.default_side_kind is not None
        n = int(has_weights) + int(has_pattern) + int(has_fixed)
        if n > 1:
            raise ValueError("side_recipe: mix of weights/pattern/fixed (R33)")
        if has_weights:
            if self.slope_weight is None or self.sheer_weight is None:
                raise ValueError("side_recipe Mode A needs both slope_weight and sheer_weight")
            if not weights_sum_ok(self.slope_weight, self.sheer_weight):
                raise ValueError(
                    f"slope_weight + sheer_weight must == 1 (±{WEIGHT_SUM_EPS})"
                )
        if self.side_kinds is not None and len(self.side_kinds) == 0:
            raise ValueError("side_recipe pattern side_kinds must be non-empty")
        return self

    def detect_mode(self) -> MountainSideRecipeMode:
        if self.slope_weight is not None and self.sheer_weight is not None:
            return MountainSideRecipeMode.WEIGHTS
        if self.side_kinds:
            return MountainSideRecipeMode.PATTERN
        if self.default_side_kind is not None:
            return MountainSideRecipeMode.FIXED
        return MountainSideRecipeMode.EMPTY
