"""Positive static contracts. Selectors must live outside Annotated metadata."""

from typing import Annotated, assert_type

from pydantic import BaseModel, computed_field

from app.dataModel.cascade.cascadeSpec import (
    CascadeChannel, CascadeDefault, CascadeLink, FieldRef,
)
from app.dataModel.locations.context.cascadeParams import SETTLEMENT_DENSITY
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.locations.settlement.enums.districtDensity import DistrictDensity

from app.application.cascade.cascadeLink import EmptyLink
from app.application.cascade.contextResolver import extend
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.locations.context.locationContext import LocationContext


class SpecializedWaterContext(WaterGenerationContext):
    marker: int = 1


def valid_concrete_contexts(location: LocationContext, water: WaterGenerationContext,
                            specialized: SpecializedWaterContext) -> None:
    assert_type(LocationContext.root(object()), LocationContext)
    assert_type(WaterGenerationContext.root(object()), WaterGenerationContext)
    assert_type(SpecializedWaterContext.root(object()), SpecializedWaterContext)
    assert_type(extend(location, EmptyLink(ScopeLevel.SETTLEMENT)), LocationContext)
    assert_type(extend(water, EmptyLink(WaterGenerationScope.WORLD)), WaterGenerationContext)
    assert_type(extend(specialized, EmptyLink(WaterGenerationScope.WORLD)), SpecializedWaterContext)
    assert_type(water.level, WaterGenerationScope)
    assert_type(water.provenance, dict[str, tuple[WaterGenerationScope, str]])
    assert_type(location.provenance, dict[str, tuple[ScopeLevel, str]])


district_density = FieldRef(lambda: DistrictTemplateEntry, lambda pojo: pojo.density)
assert_type(district_density, FieldRef[DistrictTemplateEntry, DistrictDensity | None])

# This reference is created before the model exists, just like production self-links.
self_density = FieldRef(lambda: Source, lambda pojo: pojo.density)


class Source(BaseModel):
    density: Annotated[
        DistrictDensity | None,
        CascadeChannel(
            SETTLEMENT_DENSITY, ScopeLevel.SETTLEMENT,
            above=CascadeLink(district_density, ScopeLevel.DISTRICT),
            below=CascadeLink(self_density, ScopeLevel.SETTLEMENT),
        ),
    ] = None


assert_type(self_density, FieldRef[Source, DistrictDensity | None])


class Defaults(BaseModel):
    @computed_field
    @property
    def density(self) -> DistrictDensity:
        return DistrictDensity.MEDIUM


computed_density = FieldRef(lambda: Defaults, lambda pojo: pojo.density)
assert_type(computed_density, FieldRef[Defaults, DistrictDensity])
default = CascadeDefault(computed_density)
