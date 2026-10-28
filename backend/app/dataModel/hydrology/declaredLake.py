"""Declared lake shoreline — SCH-WORLD-HYDROLOGY."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.dataModel.registryKey import RegistryKey
from app.dataModel.hydrology.placement.placementFields import WaterSourcePlacementFields
from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.materials.worldMaterialRegistry import MaterialKey, WorldMaterialRegistry


class DeclaredLake(WaterSourcePlacementFields):
    """Master declare: closed-ish lake shoreline polyline."""

    model_config = ConfigDict(extra="ignore", frozen=True, strict=False, revalidate_instances="never")

    location_uid: StrictOnWire[str]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = RegistryKey[WorldMaterialRegistry]("water")
    shoreline: DefaultWhenMissing[tuple[HydrologyWaypoint, ...]] = Field(default_factory=tuple)
