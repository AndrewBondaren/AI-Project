"""Single owners of water priorities; projections must supply actual values explicitly."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.placement.common import Specificity


class WaterSourcePlacementFields(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    placement_specificity: DefaultWhenMissing[Specificity | None] = None


class WaterCategoryPlacementFields(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    # Owning default remains zero until G10-A; None inherits the common terminal.
    placement_specificity: DefaultWhenMissing[Specificity | None] = 0
