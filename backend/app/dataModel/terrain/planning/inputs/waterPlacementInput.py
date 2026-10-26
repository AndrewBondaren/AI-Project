"""Baseline water-placement source projection; no live World or root mutable lists."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.identity.uid import EntityUid
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.planning.identity.sourceFieldRole import SourceFieldRole


class WaterAnchorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    source_uid: EntityUid
    position: FineXY
    subtype: GeographicSubtype | None


class WaterPlacementInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    enabled: StrictBool
    resolution_mode: Annotated[ResolutionMode, SourceFieldRole.EXECUTION_POLICY]
    default_water_level: FineZ
    seas: HydrologySeasPolicy
    lakes: HydrologyLakesPolicy
    basins: tuple[DeclaredBasin, ...]
    coastlines: tuple[DeclaredCoastline, ...]
    declared_lakes: tuple[DeclaredLake, ...]
    anchors: tuple[WaterAnchorInput, ...]
    topology: WorldTopology
    grid: SurfaceGridSettings
    z_min: FineZ
    z_max: FineZ
    liquid_keys: frozenset[MaterialKey]

    @model_validator(mode="after")
    def valid_levels_and_liquids(self) -> Self:
        if self.z_min > self.z_max:
            raise ValueError("z_min exceeds z_max")
        if not self.z_min <= self.default_water_level <= self.z_max:
            raise ValueError("default water level outside world z bounds")
        for basin in self.basins:
            level = basin.z_water_level if basin.z_water_level is not None else self.default_water_level
            basin.validate_water_level(self.default_water_level)
            if not self.z_min <= basin.floor_z < level <= self.z_max:
                raise ValueError("declared basin levels outside world z bounds")
        for entry in (*self.basins, *self.coastlines, *self.declared_lakes):
            if entry.liquid not in self.liquid_keys:
                raise ValueError(f"unknown liquid key: {entry.liquid}")
        return self
