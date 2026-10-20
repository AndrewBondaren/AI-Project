"""Declared coastline / sea basin shore — SCH-WORLD-HYDROLOGY."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.materials.worldMaterialRegistry import MaterialKey


class DeclaredCoastline(BaseModel):
    """Master declare: water-body intent from an open line or closed ring."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: StrictOnWire[str]
    kind: StrictOnWire[BasinKind]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = "water"
    closed: DefaultWhenMissing[bool] = False
    water_side: DefaultWhenMissing[WaterSide | None] = None
    path: DefaultWhenMissing[list[HydrologyWaypoint]] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_line(self) -> DeclaredCoastline:
        if self.closed and self.water_side is None:
            raise ValueError("closed coastline requires water_side")
        if len({(p.x, p.y) for p in self.path}) < (3 if self.closed else 2):
            raise ValueError("coastline requires distinct points: 3 for a ring, 2 for a line")
        return self
