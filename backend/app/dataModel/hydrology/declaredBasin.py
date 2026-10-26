"""Authored basin geometry and floor — HY-12, before placement/carve."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.spatial.regionShape import RegionShape


class DeclaredBasin(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: StrictOnWire[str]
    footprint: StrictOnWire[RegionShape]
    kind: StrictOnWire[BasinKind]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = "water"
    floor_z: StrictOnWire[int]
    z_water_level: DefaultWhenMissing[int | None] = None
    rim: DefaultWhenMissing[HydrologyBands | None] = None
    placement_specificity: DefaultWhenMissing[Annotated[int, constrained_field(greater_equals=0)] | None] = None

    def validate_water_level(self, default_water_level: int) -> None:
        level = self.z_water_level if self.z_water_level is not None else default_water_level
        if self.floor_z >= level:
            raise ValueError(f"basin {self.location_uid}: floor_z must be below z_water_level")

    @model_validator(mode="after")
    def explicit_level(self) -> DeclaredBasin:
        if self.rim is not None and self.rim.min > self.rim.max:
            raise ValueError("basin rim requires min <= max")
        if self.z_water_level is not None:
            self.validate_water_level(self.z_water_level)
        return self
