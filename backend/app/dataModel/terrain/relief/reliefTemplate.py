"""ReliefTemplate library outline — tz_terrain_relief R17/R26/R33."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire, StrictOnWire
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe
from app.dataModel.terrain.relief.reliefGradeKnobs import (
    reject_removed_shoulder_width,
    require_weights_pair,
    resolved_slope_length_cells,
    validate_canal_flat_refs,
    validate_canal_xor,
    validate_geom_xor,
)
from app.dataModel.terrain.relief.reliefTerrainCondition import ReliefTerrainCondition


class ReliefTemplate(BaseModel):
    """Global library blob / pack JSON body (not stored inline on world)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_name: StrictOnWire[str]
    display_name: StrictOnWire[str]
    context: StrictEnumOnWire[ReliefContext]
    conditions: DefaultOnWire[list[ReliefTerrainCondition]] = Field(default_factory=list)
    side_recipe: DefaultOnWire[MountainSideRecipe | None] = None
    # root defaults when conditions empty / case does not override (R36b Geom XOR)
    slope_length_cells: DefaultOnWire[int | None] = None
    target_angle_deg: DefaultOnWire[float | None] = None
    slope_weight: DefaultOnWire[float | None] = None
    sheer_weight: DefaultOnWire[float | None] = None
    earthen_canal: DefaultOnWire[bool | None] = None
    structure_canal: DefaultOnWire[str | None] = None
    structure_refs: DefaultOnWire[list[str]] = Field(default_factory=list)
    version: DefaultOnWire[str] = "1.0"

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy_width(cls, data: Any) -> Any:
        return reject_removed_shoulder_width(data)

    @model_validator(mode="after")
    def _context_body_rules(self) -> ReliefTemplate:
        if self.context == ReliefContext.MOUNTAIN:
            if self.conditions:
                raise ValueError(
                    "context=mountain must not carry Mode A/B conditions (R33)"
                )
        else:
            if self.side_recipe is not None:
                raise ValueError(
                    f"context={self.context.value} must not carry side_recipe (R33)"
                )
            terrains = [c.terrain for c in self.conditions]
            if len(terrains) != len(set(terrains)):
                raise ValueError("duplicate conditions.terrain (R26)")
            modes = {c.is_mode_a for c in self.conditions}
            if len(modes) > 1:
                raise ValueError("all template conditions must share Mode A or Mode B")

        if self.slope_weight is not None or self.sheer_weight is not None:
            require_weights_pair(
                self.slope_weight,
                self.sheer_weight,
                missing="root slope_weight and sheer_weight must both be set",
            )
        validate_geom_xor(self.slope_length_cells, self.target_angle_deg)
        validate_canal_xor(self.earthen_canal, self.structure_canal)
        validate_canal_flat_refs(self.structure_canal, self.structure_refs)
        return self

    def outward_length_cells(self) -> int:
        return resolved_slope_length_cells(self.slope_length_cells)

    def condition_for(self, terrain: str) -> ReliefTerrainCondition | None:
        for cond in self.conditions:
            if cond.terrain.value == terrain:
                return cond
        return None
