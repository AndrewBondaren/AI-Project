from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode


class PlateCountAdjustedNotice(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")

    code: Literal[WaterDesignIssueCode.PLATE_COUNT_ADJUSTED] = WaterDesignIssueCode.PLATE_COUNT_ADJUSTED
    requested: StrictInt
    effective: StrictInt = Field(gt=0)

    @model_validator(mode="after")
    def reduced_count(self) -> Self:
        if self.effective >= self.requested:
            raise ValueError("effective plate count must be below requested count")
        return self
