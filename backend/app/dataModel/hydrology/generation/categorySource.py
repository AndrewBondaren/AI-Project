"""Typed category bindings declared by each captured hydrology input owner."""

from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.generation.waterGenerationSettings import CategoryWaterGenerationSettings
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy


@dataclass(frozen=True)
class HydrologyCategorySource[M: BaseModel]:
    category: WaterGenerationCategory
    policy: FieldRef[M, HydrologySeasPolicy | HydrologyLakesPolicy]
    generation: FieldRef[M, CategoryWaterGenerationSettings]


class HydrologyCategoryFields(BaseModel):
    """Required captured category fields, shared by placement and classification."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    sea_generation: CategoryWaterGenerationSettings
    ocean_generation: CategoryWaterGenerationSettings
    lake_generation: CategoryWaterGenerationSettings
    seas: HydrologySeasPolicy
    lakes: HydrologyLakesPolicy

    category_sources: ClassVar[tuple[HydrologyCategorySource["HydrologyCategoryFields"], ...]] = (
        HydrologyCategorySource(WaterGenerationCategory.LAKE,
            FieldRef(lambda: HydrologyCategoryFields, lambda s: s.lakes),
            FieldRef(lambda: HydrologyCategoryFields, lambda s: s.lake_generation)),
        HydrologyCategorySource(WaterGenerationCategory.OCEAN,
            FieldRef(lambda: HydrologyCategoryFields, lambda s: s.seas),
            FieldRef(lambda: HydrologyCategoryFields, lambda s: s.ocean_generation)),
        HydrologyCategorySource(WaterGenerationCategory.SEA,
            FieldRef(lambda: HydrologyCategoryFields, lambda s: s.seas),
            FieldRef(lambda: HydrologyCategoryFields, lambda s: s.sea_generation)),
    )

    @classmethod
    def category_source(cls, category: WaterGenerationCategory) -> HydrologyCategorySource["HydrologyCategoryFields"]:
        if not isinstance(category, WaterGenerationCategory):
            raise ValueError("category binding requires a water generation category")
        return next(binding for binding in cls.category_sources if binding.category is category)
