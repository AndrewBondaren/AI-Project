"""Shared climate point/sample definitions; old generator paths re-export these."""

from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, Field, StrictInt
from pydantic.dataclasses import dataclass

from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.enums.poleSource import PoleSource
from app.dataModel.identity.uid import EntityUid
from app.dataModel.registryKey import RegistryKey
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY


type ClimateKey = RegistryKey[WorldClimateZoneRegistry]


class AnchorSource(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"
    ADMIN = "admin"


@dataclass(frozen=True, config=ConfigDict(extra="forbid", revalidate_instances="always"))
class ClimatePolePoint:
    gx: Annotated[GridX, Field(strict=True)]
    gy: Annotated[GridY, Field(strict=True)]
    pole_kind: PoleKind
    system_climate_zone: ClimateKey
    base_temperature: StrictInt
    weight: Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
    location_uid: EntityUid | None
    source: PoleSource


@dataclass(frozen=True, config=ConfigDict(extra="forbid", revalidate_instances="always"))
class ClimateAnchorPoint:
    """Single Voronoi center — one grid cell, not a footprint."""

    gx: Annotated[GridX, Field(strict=True)]
    gy: Annotated[GridY, Field(strict=True)]
    system_climate_zone: ClimateKey
    location_uid: EntityUid | None
    source: AnchorSource


@dataclass(frozen=True, config=ConfigDict(extra="forbid", revalidate_instances="always"))
class PoleClimateSample:
    system_climate_zone: ClimateKey
    zone_location_uid: EntityUid | None
    typical_elevation_z: StrictInt
    base_temperature_override: StrictInt | None
