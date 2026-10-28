"""One nullable schema and one linked VALUE graph for embedded source POJOs."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.dataModel.annotationPolicy import DefaultEnumWhenMissing, DefaultWhenMissing
from app.dataModel.cascade.cascadeSpec import (
    Cascade, CascadeChannel, CascadeDefault, CascadeLink, ChannelKind, DefaultPolicy, FieldRef,
)
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterFraction, WaterGenerationDefaults
from app.dataModel.hydrology.generation.legacySettings import normalize_seas_generation, normalize_lakes_generation
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind

WATER_FRACTION = Cascade("water_fraction", DefaultPolicy.CANONICAL_DEFAULT, Scope,
    default_source=CascadeDefault(FieldRef(lambda: WaterGenerationDefaults, lambda d: d.water_fraction)),
    input_types=((ChannelKind.VALUE, float),))
WATER_AUTORESOLVE = Cascade("autoresolve", DefaultPolicy.CANONICAL_DEFAULT, Scope,
    default_source=CascadeDefault(FieldRef(lambda: WaterGenerationDefaults, lambda d: d.autoresolve)),
    input_types=((ChannelKind.VALUE, bool),))
WATER_STRATEGY = Cascade("strategy", DefaultPolicy.CANONICAL_DEFAULT, Scope,
    default_source=CascadeDefault(FieldRef(lambda: WaterGenerationDefaults, lambda d: d.strategy)),
    input_types=((ChannelKind.VALUE, DesignedWaterStrategyKind),))

_WORLD_FRACTION = FieldRef(lambda: WorldWaterGenerationSettings, lambda s: s.water_fraction)
_WORLD_AUTORESOLVE = FieldRef(lambda: WorldWaterGenerationSettings, lambda s: s.autoresolve)
_WORLD_STRATEGY = FieldRef(lambda: WorldWaterGenerationSettings, lambda s: s.strategy)
_CATEGORY_FRACTION = FieldRef(lambda: CategoryWaterGenerationSettings, lambda s: s.water_fraction)
_CATEGORY_AUTORESOLVE = FieldRef(lambda: CategoryWaterGenerationSettings, lambda s: s.autoresolve)
_CATEGORY_STRATEGY = FieldRef(lambda: CategoryWaterGenerationSettings, lambda s: s.strategy)


class WaterGenerationSettings(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always", validate_default=True)

    water_fraction: DefaultWhenMissing[WaterFraction | None] = None
    autoresolve: DefaultWhenMissing[StrictBool | None] = None
    strategy: DefaultEnumWhenMissing[DesignedWaterStrategyKind | None] = None


class WorldWaterGenerationSettings(WaterGenerationSettings, frozen=True):
    water_fraction: Annotated[DefaultWhenMissing[WaterFraction | None],
                              CascadeChannel(WATER_FRACTION, Scope.WORLD)] = None
    autoresolve: Annotated[DefaultWhenMissing[StrictBool | None],
                          CascadeChannel(WATER_AUTORESOLVE, Scope.WORLD)] = None
    strategy: Annotated[DefaultEnumWhenMissing[DesignedWaterStrategyKind | None],
                       CascadeChannel(WATER_STRATEGY, Scope.WORLD)] = None


class CategoryWaterGenerationSettings(WaterGenerationSettings, frozen=True):
    water_fraction: Annotated[DefaultWhenMissing[WaterFraction | None], CascadeChannel(WATER_FRACTION, Scope.CATEGORY,
        below=CascadeLink(_WORLD_FRACTION, Scope.WORLD))] = None
    autoresolve: Annotated[DefaultWhenMissing[StrictBool | None], CascadeChannel(WATER_AUTORESOLVE, Scope.CATEGORY,
        below=CascadeLink(_WORLD_AUTORESOLVE, Scope.WORLD))] = None
    strategy: Annotated[DefaultEnumWhenMissing[DesignedWaterStrategyKind | None], CascadeChannel(WATER_STRATEGY, Scope.CATEGORY,
        below=CascadeLink(_WORLD_STRATEGY, Scope.WORLD))] = None


class BodyWaterGenerationSettings(WaterGenerationSettings, frozen=True):
    water_fraction: Annotated[DefaultWhenMissing[WaterFraction | None], CascadeChannel(WATER_FRACTION, Scope.WATER_BODY,
        below=CascadeLink(_CATEGORY_FRACTION, Scope.CATEGORY))] = None
    autoresolve: Annotated[DefaultWhenMissing[StrictBool | None], CascadeChannel(WATER_AUTORESOLVE, Scope.WATER_BODY,
        below=CascadeLink(_CATEGORY_AUTORESOLVE, Scope.CATEGORY))] = None
    strategy: Annotated[DefaultEnumWhenMissing[DesignedWaterStrategyKind | None], CascadeChannel(WATER_STRATEGY, Scope.WATER_BODY,
        below=CascadeLink(_CATEGORY_STRATEGY, Scope.CATEGORY))] = None


class WorldHydrologyGenerationFields(BaseModel, frozen=True):
    """Future root owner fields; active WorldHydrology switches at G10-A."""

    model_config = WaterGenerationSettings.model_config
    enabled: DefaultWhenMissing[StrictBool] = True
    generation: DefaultWhenMissing[WorldWaterGenerationSettings] = Field(default_factory=WorldWaterGenerationSettings)


class SeasGenerationFields(BaseModel, frozen=True):
    """Reusable fields for the future sea owner; no legacy fields in the schema."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")
    sea_generation: DefaultWhenMissing[CategoryWaterGenerationSettings] = Field(default_factory=CategoryWaterGenerationSettings)
    ocean_generation: DefaultWhenMissing[CategoryWaterGenerationSettings] = Field(default_factory=CategoryWaterGenerationSettings)

    @model_validator(mode="before")
    @classmethod
    def legacy_generation(cls, value: object) -> object:
        return normalize_seas_generation(value)


class LakesGenerationFields(BaseModel, frozen=True):
    """Reusable lake owner field; rivers retain their existing category policy."""

    model_config = SeasGenerationFields.model_config
    generation: DefaultWhenMissing[CategoryWaterGenerationSettings] = Field(default_factory=CategoryWaterGenerationSettings)

    @model_validator(mode="before")
    @classmethod
    def legacy_generation(cls, value: object) -> object:
        return normalize_lakes_generation(value)
