"""Typed category bindings declared by each captured hydrology input owner."""

from dataclasses import dataclass

from pydantic import BaseModel

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
