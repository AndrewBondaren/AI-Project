"""One `worlds.material_registry[]` row — N1-W-01."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.policy import OptionalOnWire, StrictOnWire

HARDNESS_MIN = 1
HARDNESS_MAX = 5


class MaterialRegistryEntry(BaseModel):
    """tz_materials.md §2 — physics + generator material row."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_material: StrictOnWire[str]
    display_name: StrictOnWire[str]
    glossary_ref: OptionalOnWire[str | None] = None
    material_category: StrictOnWire[str]
    tags: OptionalOnWire[list[str]] = Field(default_factory=list)
    use_type: OptionalOnWire[list[str]] = Field(default_factory=list)
    economic_tier: OptionalOnWire[str | None] = None
    hardness: OptionalOnWire[int | None] = Field(default=None, ge=HARDNESS_MIN, le=HARDNESS_MAX)
    density: OptionalOnWire[int | None] = Field(default=None, ge=1)
    heat_conductivity: OptionalOnWire[float] = Field(default=0.1, ge=0.0, le=1.0)
    viscosity: OptionalOnWire[float | None] = Field(default=None, ge=0.0, le=1.0)
    heat_into: OptionalOnWire[str | None] = None
    heat_temp: OptionalOnWire[int | None] = None
    cool_into: OptionalOnWire[str | None] = None
    cool_temp: OptionalOnWire[int | None] = None
    structural_strength: OptionalOnWire[float | None] = Field(default=None, ge=0.0, le=1.0)
    flammable: OptionalOnWire[bool] = False
    freezable: OptionalOnWire[bool] = False
    corrodible: OptionalOnWire[bool] = True
    meltable: OptionalOnWire[bool] = False
    mineable: OptionalOnWire[bool] = False
    transparent: OptionalOnWire[bool] = False
    breakable: OptionalOnWire[bool] = False
    temp_damage: OptionalOnWire[bool] = False
    vision_block: OptionalOnWire[bool] = False
    components: OptionalOnWire[list[str] | None] = None
