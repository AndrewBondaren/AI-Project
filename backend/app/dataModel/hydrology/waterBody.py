"""Physical water-body facts; shared system identity/lifecycle belongs to W/L."""

from typing import Self

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.materials.worldMaterialRegistry import MaterialKey


class WaterBody(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    water_body_uid: StrictOnWire[str]
    location_uid: DefaultWhenMissing[str | None] = None
    kind: StrictOnWire[BasinKind]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = "water"
    declared_level: StrictOnWire[int]
    z_water_level: StrictOnWire[int]
    declared_basin_uid: DefaultWhenMissing[str | None] = None
    parent_system_uid: DefaultWhenMissing[str | None] = None

    def with_parent_system(self, parent_system_uid: str | None) -> Self:
        return type(self).model_validate(self.model_dump(round_trip=True, by_alias=True) | {
            "parent_system_uid": parent_system_uid,
        })
