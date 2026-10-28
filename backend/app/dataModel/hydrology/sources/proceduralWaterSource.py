"""Authored procedural intent, without fabricated geometry or resolved policy."""

from typing import Self

from pydantic import ConfigDict, Field, model_validator

from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.generation.waterGenerationSettings import BodyWaterGenerationSettings
from app.dataModel.identity.uid import EntityUid
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.hydrology.placement.placementFields import WaterSourcePlacementFields
from app.dataModel.spatial.grid.coordinateTypes import FineZ


class ProceduralWaterSource(WaterSourcePlacementFields):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    source_uid: EntityUid
    generation_region_uid: EntityUid
    kind: BasinKind
    liquid: MaterialKey
    z_water_level: FineZ | None = None
    generation: BodyWaterGenerationSettings = Field(default_factory=BodyWaterGenerationSettings)

    @model_validator(mode="after")
    def single_region_binding(self) -> Self:
        if self.generation.generation_region_uid is not None:
            raise ValueError("procedural generation region belongs only to the source")
        return self
