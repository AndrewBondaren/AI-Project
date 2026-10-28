"""Coverage values in fine²; calculation belongs to the common budget policy."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterFraction
from app.dataModel.identity.uid import EntityUid

type FineArea = Annotated[StrictInt, Field(ge=0)]


class _CoverageRecord(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")


class BodyCoverageRequest(_CoverageRecord, frozen=True):
    source_uid: EntityUid
    generation_region_uid: EntityUid
    generation_area_fine2: FineArea
    target_fraction: WaterFraction


class BodyCoverageAllocation(_CoverageRecord, frozen=True):
    source_uid: EntityUid
    generation_region_uid: EntityUid
    requested_fine2: FineArea
    allocated_fine2: FineArea

    @model_validator(mode="after")
    def bounded_allocation(self) -> Self:
        if self.allocated_fine2 > self.requested_fine2:
            raise ValueError("allocation exceeds request")
        return self


class WaterCoverageBudget(_CoverageRecord, frozen=True):
    region_uid: EntityUid
    area_fine2: FineArea
    target_fraction: WaterFraction
    target_fine2: FineArea
    authored_union_fine2: FineArea
    residual_fine2: FineArea
    allocations: tuple[BodyCoverageAllocation, ...]

    @model_validator(mode="after")
    def bounded_budget(self) -> Self:
        if self.target_fine2 > self.area_fine2 or self.authored_union_fine2 > self.area_fine2:
            raise ValueError("water area exceeds region area")
        if self.residual_fine2 != max(0, self.target_fine2 - self.authored_union_fine2):
            raise ValueError("residual must be target minus authored union, bounded at zero")
        if len({a.source_uid for a in self.allocations}) != len(self.allocations):
            raise ValueError("duplicate source allocation")
        if sum(a.allocated_fine2 for a in self.allocations) > min(
                self.residual_fine2, self.area_fine2 - self.authored_union_fine2):
            raise ValueError("allocations exceed common residual or unauthored area")
        return self
