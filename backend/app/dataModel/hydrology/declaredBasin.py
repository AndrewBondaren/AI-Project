"""Authored basin geometry and floor — HY-12, before placement/carve."""

from __future__ import annotations

from pydantic import ConfigDict, model_validator

from app.dataModel.registryKey import RegistryKey
from app.dataModel.hydrology.placement.placementFields import WaterSourcePlacementFields
from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.materials.worldMaterialRegistry import MaterialKey, WorldMaterialRegistry
from app.dataModel.spatial.regionShape import RegionShape


class DeclaredBasin(WaterSourcePlacementFields):
    model_config = ConfigDict(extra="ignore", frozen=True, strict=False, revalidate_instances="never")

    location_uid: StrictOnWire[str]
    footprint: StrictOnWire[RegionShape]
    kind: StrictOnWire[BasinKind]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = RegistryKey[WorldMaterialRegistry]("water")
    floor_z: StrictOnWire[int]
    z_water_level: DefaultWhenMissing[int | None] = None
    rim: DefaultWhenMissing[HydrologyBands | None] = None

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
