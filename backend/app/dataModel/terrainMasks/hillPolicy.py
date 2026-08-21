"""Hill knobs for open-land **consumers** (plains / forest) — not a mask domain.

Helper raster reads a resolved instance; it does not load world JSON.
SoT wire: ``docs/tz_world_pack_storage.md`` § L2 open-land hills.
Template: ``fixtures/world_template.json`` ``terrain_masks.default_*.hills``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.terrainMasks.hillShape import HillShape


class HillPolicy(BaseModel):
    """Consumer → helper: gap, footprint, height, shape palette."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    min_spacing: DefaultOnWire[int] = constrained_field(default=500, greater_equals=1)
    radius: DefaultOnWire[int] = constrained_field(default=40, greater_equals=1)
    height: DefaultOnWire[int] = constrained_field(default=2, greater_equals=1)
    shapes: DefaultOnWire[tuple[HillShape, ...]] = Field(default_factory=tuple)

    @field_validator("shapes", mode="before")
    @classmethod
    def _shapes_tuple(cls, value: object) -> object:
        if value is None:
            return ()
        return value

    def resolved_shapes(self) -> tuple[HillShape, ...]:
        """Palette for one hill. Empty wire → full catalog (hash from world uid)."""
        if self.shapes:
            return self.shapes
        return HillShape.catalog()

    @classmethod
    def canonical_plains(cls) -> HillPolicy:
        """``default_plains.hills`` / Field defaults — keep in sync with world_template."""
        return cls()

    @classmethod
    def canonical_forest(cls) -> HillPolicy:
        """``default_forests.hills`` — keep in sync with world_template."""
        return cls(radius=25)
