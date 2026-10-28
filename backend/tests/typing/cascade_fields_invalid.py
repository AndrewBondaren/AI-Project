"""Expected diagnostics, checked by scripts/check-cascade-types.cjs."""

from pydantic import BaseModel

from app.dataModel.cascade.cascadeSpec import FieldRef


class Source(BaseModel):
    value: str = "value"


class Other(BaseModel):
    number: int = 1


from app.application.cascade.cascadeLink import EmptyLink
from app.application.cascade.contextResolver import extend
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.context.scopeLevel import ScopeLevel


def invalid_context_axes(water: WaterGenerationContext) -> None:
    WaterGenerationContext(level=ScopeLevel.WORLD)  # expect: reportArgumentType
    LocationContext(level=WaterGenerationScope.WORLD)  # expect: reportArgumentType
    water.provenance["fraction"] = (ScopeLevel.WORLD, "authored")  # expect: reportArgumentType


def invalid_concrete_context_return(water: WaterGenerationContext) -> LocationContext:
    return extend(water, EmptyLink(WaterGenerationScope.WORLD))  # expect: reportReturnType


from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings, BodyWaterGenerationSettings
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind


def invalid_water_settings(source: WorldWaterGenerationSettings) -> None:
    WorldWaterGenerationSettings(autoresolve=1)  # expect: reportArgumentType
    BodyWaterGenerationSettings(strategy=ScopeLevel.WORLD)  # expect: reportArgumentType
    WorldWaterGenerationSettings(strategy="plate")  # expect: reportArgumentType
    source.autoresolve = False  # expect: reportAttributeAccessIssue
    ref: FieldRef[WorldWaterGenerationSettings, DesignedWaterStrategyKind | None] = FieldRef(lambda: WorldWaterGenerationSettings, lambda s: s.autoresolve)  # expect: reportAssignmentType


from app.dataModel.hydrology.generation.waterGenerationSettings import SeasGenerationFields, LakesGenerationFields, BodyGenerationFields


def invalid_category_owner_fields(source: SeasGenerationFields) -> None:
    SeasGenerationFields(sea_generation=WorldWaterGenerationSettings())  # expect: reportArgumentType
    LakesGenerationFields(generation=True)  # expect: reportArgumentType
    source.sea_generation = source.ocean_generation  # expect: reportAttributeAccessIssue


def invalid_body_owner_field(source: BodyGenerationFields) -> None:
    BodyGenerationFields(generation=WorldWaterGenerationSettings())  # expect: reportArgumentType
    BodyGenerationFields(generation=False)  # expect: reportArgumentType
    source.generation = BodyWaterGenerationSettings()  # expect: reportAttributeAccessIssue


missing = FieldRef(lambda: Source, lambda pojo: pojo.missing)  # expect: reportAttributeAccessIssue
self_missing = FieldRef(lambda: Later, lambda pojo: pojo.missing)  # expect: reportAttributeAccessIssue


class Later(BaseModel):
    value: str = "value"


def wrong_selector(pojo: Other) -> str:
    return str(pojo.number)


wrong_model: FieldRef[Source, str] = FieldRef(lambda: Source, wrong_selector)  # expect: reportArgumentType
wrong_value: FieldRef[Source, int] = FieldRef(lambda: Source, lambda pojo: pojo.value)  # expect: reportAssignmentType


from app.dataModel.cascade.runtimeContext import freeze_resolved_context
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext


def requires_resolved_context(context: ResolvedWaterGenerationContext) -> None:
    pass


def invalid_resolved_context(runtime: WaterGenerationContext, resolved: ResolvedWaterGenerationContext) -> None:
    requires_resolved_context(runtime)  # expect: reportArgumentType
    freeze_resolved_context(runtime, WaterGenerationContext)  # expect: reportArgumentType
    ResolvedWaterGenerationContext(level=ScopeLevel.WORLD, provenance=(), water_fraction=0.0, autoresolve=False, strategy=DesignedWaterStrategyKind.PLATE)  # expect: reportArgumentType
    resolved.autoresolve = True  # expect: reportAttributeAccessIssue
