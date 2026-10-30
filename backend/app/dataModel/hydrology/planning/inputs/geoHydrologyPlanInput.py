"""Captured authored hydrology settings; execution decisions arrive from providers."""

from typing import Annotated, Self

from pydantic import ConfigDict, StrictBool, StrictInt, field_validator, model_validator

from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, validate_declared_rivers_topology
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.hydrologyScope import HYDROLOGY_BOOTSTRAP_SCOPES, HydrologyScope
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.generation.categorySource import HydrologyCategoryFields
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyAnchorInput
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.identity.uid import EntityUid
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.planning.identity.sourceFieldRole import SourceFieldRole
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.validation.immutableValue import validate_immutable


class GeoHydrologyPlanInput(HydrologyCategoryFields):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    enabled: StrictBool
    generation: WorldWaterGenerationSettings
    defaults: WaterGenerationDefaults
    seed: StrictInt
    resolution_mode: Annotated[ResolutionMode, SourceFieldRole.EXECUTION_POLICY]
    scopes: frozenset[HydrologyScope]
    default_water_level: FineZ
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
    allowed_body_kinds: frozenset[BasinKind]

    @field_validator("seas", "lakes", "rivers", "topology", mode="before")
    @classmethod
    def revalidate_sources(cls, value: object) -> object:
        if isinstance(value, (HydrologySeasPolicy, HydrologyLakesPolicy, HydrologyRiversPolicy, WorldTopology)):
            validate_immutable(value)
            return type(value).model_validate(value.model_dump(warnings=False), strict=True)
        return value

    @model_validator(mode="after")
    def complete_sources(self) -> Self:
        validate_immutable(self)
        if not self.z_min <= self.default_water_level <= self.z_max:
            raise ValueError("default water level outside world z bounds")
        if not self.scopes <= HYDROLOGY_BOOTSTRAP_SCOPES:
            raise ValueError("planning supports only bootstrap hydrology scopes")
        if len({anchor.location_uid for anchor in self.anchors}) != len(self.anchors):
            raise ValueError("duplicate hydrology anchor UID")
        for source in (*self.coastlines, *self.declared_lakes):
            if source.liquid not in self.liquid_keys:
                raise ValueError("hydrology source liquid is absent from captured material membership")
        validate_declared_rivers_topology(list(self.declared_rivers))
        return self
