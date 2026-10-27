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


missing = FieldRef(lambda: Source, lambda pojo: pojo.missing)  # expect: reportAttributeAccessIssue
self_missing = FieldRef(lambda: Later, lambda pojo: pojo.missing)  # expect: reportAttributeAccessIssue


class Later(BaseModel):
    value: str = "value"


def wrong_selector(pojo: Other) -> str:
    return str(pojo.number)


wrong_model: FieldRef[Source, str] = FieldRef(lambda: Source, wrong_selector)  # expect: reportArgumentType
wrong_value: FieldRef[Source, int] = FieldRef(lambda: Source, lambda pojo: pojo.value)  # expect: reportAssignmentType
