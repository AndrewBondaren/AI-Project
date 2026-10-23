"""Source projections for route planning and final water-fact assembly."""

from typing import Self

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, model_validator

from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, validate_declared_rivers_topology
from app.dataModel.hydrology.enums.planning.hydrologyScope import HYDROLOGY_BOOTSTRAP_SCOPES, HydrologyScope
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.identity.uid import EntityUid
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


class HydrologyAnchorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    location_uid: EntityUid
    position: FineXY | None
    z: FineZ | None
    subtype: GeographicSubtype | None


class HydrologyPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    enabled: StrictBool
    seed: StrictInt
    resolution_mode: ResolutionMode
    scopes: frozenset[HydrologyScope]
    default_water_level: FineZ
    seas: HydrologySeasPolicy
    lakes: HydrologyLakesPolicy
    rivers: HydrologyRiversPolicy
    declared_rivers: tuple[DeclaredRiver, ...]
    coastlines: tuple[DeclaredCoastline, ...]
    declared_lakes: tuple[DeclaredLake, ...]
    anchors: tuple[HydrologyAnchorInput, ...]
    topology: WorldTopology
    grid: SurfaceGridSettings
    z_min: FineZ
    z_max: FineZ
    liquid_keys: frozenset[MaterialKey]
    change_uid: EntityUid

    @model_validator(mode="after")
    def valid_inputs(self) -> Self:
        if self.z_min > self.z_max:
            raise ValueError("z_min exceeds z_max")
        if not self.scopes <= HYDROLOGY_BOOTSTRAP_SCOPES:
            raise ValueError("planning supports only bootstrap hydrology scopes")
        for entry in (*self.coastlines, *self.declared_lakes):
            if entry.liquid not in self.liquid_keys:
                raise ValueError(f"unknown hydrology liquid key: {entry.liquid}")
        validate_declared_rivers_topology(list(self.declared_rivers))
        return self


class HydrologyFinalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    enabled: StrictBool
    grid: SurfaceGridSettings
    topology: WorldTopology
