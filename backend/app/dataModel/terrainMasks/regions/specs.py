"""Coverage declarations — tz_map_light_bake § Регионы покрытия."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.dataModel.spatial.regionShape import AnchorRadiusShape, RegionShape
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.ids.regionIdentity import normalize_region_name


class RegionSpecBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    IDENTITY_SOURCE: ClassVar[str] = "declared"

    name: str | None = Field(default=None, validate_default=True)
    shape: RegionShape
    density: float = Field(default=1.0, ge=0.0, le=1.0, allow_inf_nan=False)
    placement_specificity: int | None = Field(default=None, ge=0)
    location_uid: str | None = None

    @field_validator("name")
    @classmethod
    def declared_name(cls, value: str | None, info: ValidationInfo) -> str | None:
        name = normalize_region_name(value)
        if not name and info.context and info.context.get("validate_only"):
            raise ValueError("declared region name is required for author validation")
        return name or None

    def identity_key(self) -> tuple[object, ...]:
        """Geometry/type edits preserve named identity; UID generation is separate."""
        if self.name is not None:
            return (self.IDENTITY_SOURCE, self.name)
        if isinstance(self.shape, AnchorRadiusShape):
            return (self.IDENTITY_SOURCE, self.shape.kind, self.shape.anchor_uid)
        x_min, y_min, _, _ = self.shape.bbox()
        return (self.IDENTITY_SOURCE, self.shape.kind, x_min, y_min)


class ForestSpec(RegionSpecBase):
    # Точка расширения: состав — docs/tz_flora.md, поля flora нет — unknown key.
    entry_type: Literal["forest"] = Field(
        default_factory=WorldTerrainRegistry.forest_terrain_key, validate_default=True,
    )


class PlainSpec(RegionSpecBase):
    entry_type: Literal["plains"] = Field(
        default_factory=WorldTerrainRegistry.plains_terrain_key, validate_default=True,
    )


class FarmlandSpec(RegionSpecBase):
    # Точка расширения: состав — docs/tz_flora.md; crop ждёт crops_registry,
    # поля нет — unknown key.
    entry_type: Literal["farmland"] = Field(
        default_factory=WorldTerrainRegistry.farmland_terrain_key, validate_default=True,
    )


LandcoverDeclareEntry = Annotated[
    ForestSpec | PlainSpec | FarmlandSpec,
    Field(discriminator="entry_type"),
]
