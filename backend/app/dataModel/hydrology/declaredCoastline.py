"""Declared coastline / sea basin shore — SCH-WORLD-HYDROLOGY."""

from __future__ import annotations

from enum import StrEnum

from pydantic import ConfigDict, Field, model_validator

from app.dataModel.hydrology.placement.placementFields import WaterSourcePlacementFields
from app.dataModel.annotationPolicy import DefaultEnumWhenMissing, DefaultWhenMissing, StrictOnWire
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.materials.worldMaterialRegistry import MaterialKey, WorldMaterialRegistry
from app.dataModel.identity.uid import EntityUid
from app.dataModel.registryKey import RegistryKey


class CoastlinePurpose(StrEnum):
    """Authored line creates water or attaches a boundary to an existing source."""

    WATER_SOURCE = "water_source"
    BODY_BOUNDARY = "body_boundary"


class DeclaredCoastline(WaterSourcePlacementFields):
    """One authored line with explicit source/boundary purpose, never a body ID."""

    model_config = ConfigDict(extra="ignore", frozen=True, strict=False, revalidate_instances="never")

    location_uid: StrictOnWire[str]
    purpose: DefaultEnumWhenMissing[CoastlinePurpose] = CoastlinePurpose.WATER_SOURCE
    # This refers to the target's source identity; G5-CP/G5-C3 resolve its
    # admission and physical mapping. The wire model never searches nearby water.
    target_source_uid: DefaultWhenMissing[EntityUid | None] = None
    kind: StrictOnWire[BasinKind]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = RegistryKey[WorldMaterialRegistry]("water")
    closed: DefaultWhenMissing[bool] = False
    water_side: DefaultWhenMissing[WaterSide | None] = None
    path: DefaultWhenMissing[tuple[HydrologyWaypoint, ...]] = Field(default_factory=tuple)

    @property
    def is_water_source(self) -> bool:
        """Structural routing only; no terrain/policy/priority decision."""
        return self.purpose is CoastlinePurpose.WATER_SOURCE

    @model_validator(mode="after")
    def valid_line(self) -> DeclaredCoastline:
        if self.purpose is CoastlinePurpose.BODY_BOUNDARY and self.target_source_uid is None:
            raise ValueError("body_boundary requires target_source_uid")
        if self.is_water_source and self.target_source_uid is not None:
            raise ValueError("water_source cannot bind target_source_uid")
        if self.closed and self.water_side is None:
            raise ValueError("closed coastline requires water_side")
        if len({(p.x, p.y) for p in self.path}) < (3 if self.closed else 2):
            raise ValueError("coastline requires distinct points: 3 for a ring, 2 for a line")
        return self
