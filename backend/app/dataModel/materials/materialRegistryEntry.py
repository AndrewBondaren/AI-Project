"""One `worlds.material_registry[]` row — N1-W-01."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictEnumOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.materials.enums.materialCategory import MaterialCategory
from app.dataModel.registryKey import RegistryKey

if TYPE_CHECKING:
    from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry

HARDNESS_MIN = 1
HARDNESS_MAX = 5


class MaterialRegistryEntry(BaseModel):
    """tz_materials.md §2 — physics + generator material row."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_material: StrictOnWire[RegistryKey[WorldMaterialRegistry]]
    display_name: StrictOnWire[str]
    glossary_ref: DefaultWhenMissing[str | None] = None
    material_category: StrictEnumOnWire[MaterialCategory]
    tags: DefaultWhenMissing[list[str]] = Field(default_factory=list)
    use_type: DefaultWhenMissing[list[str]] = Field(default_factory=list)
    economic_tier: DefaultWhenMissing[EconomyTierKey | None] = None
    hardness: DefaultWhenMissing[Annotated[int, Field(ge=HARDNESS_MIN, le=HARDNESS_MAX)] | None] = constrained_field(default=None)
    density: DefaultWhenMissing[Annotated[int, Field(ge=1)] | None] = constrained_field(default=None)
    heat_conductivity: DefaultWhenMissing[float] = constrained_field(
        default=0.1, greater_equals=0.0, lesser_equals=1.0,
    )
    viscosity: DefaultWhenMissing[Annotated[float, Field(ge=0.0, le=1.0)] | None] = constrained_field(default=None)
    heat_into: DefaultWhenMissing[str | None] = None
    heat_temp: DefaultWhenMissing[int | None] = None
    cool_into: DefaultWhenMissing[str | None] = None
    cool_temp: DefaultWhenMissing[int | None] = None
    structural_strength: DefaultWhenMissing[Annotated[float, Field(ge=0.0, le=1.0)] | None] = constrained_field(default=None)
    flammable: DefaultWhenMissing[bool] = False
    freezable: DefaultWhenMissing[bool] = False
    corrodible: DefaultWhenMissing[bool] = True
    meltable: DefaultWhenMissing[bool] = False
    mineable: DefaultWhenMissing[bool] = False
    transparent: DefaultWhenMissing[float] = constrained_field(
        default=0.0, greater_equals=0.0, lesser_equals=100.0,
        strict=True, allow_inf_nan=False,
    )
    breakable: DefaultWhenMissing[bool] = False
    temp_damage: DefaultWhenMissing[bool] = False
    vision_block: DefaultWhenMissing[bool] = False
    components: DefaultWhenMissing[list[str] | None] = None
