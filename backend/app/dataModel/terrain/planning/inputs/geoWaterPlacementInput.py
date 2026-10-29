"""Complete authored GEO water input, before cascade, admission and design."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator, model_validator

from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSource, ProceduralSource
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.planning.identity.sourceFieldRole import SourceFieldRole
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterAnchorInput
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.validation.immutableValue import validate_immutable


class GeoWaterPlacementInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    enabled: StrictBool
    resolution_mode: Annotated[ResolutionMode, SourceFieldRole.EXECUTION_POLICY]
    declared_world_bounds: WorldBounds | None
    default_water_level: FineZ
    generation: WorldWaterGenerationSettings
    defaults: WaterGenerationDefaults
    seas: HydrologySeasPolicy
    lakes: HydrologyLakesPolicy
    sources: tuple[WaterDesignSource, ...]
    anchors: tuple[WaterAnchorInput, ...]
    topology: WorldTopology
    grid: SurfaceGridSettings
    z_min: FineZ
    z_max: FineZ
    liquid_keys: frozenset[MaterialKey]
    noise_policy: ContinentalNoisePolicy
    plate_policy: PlateGenerationPolicy
    composition_policy: FieldCompositionPolicy
    selection_policy: WaterFieldSelectionPolicy

    @field_validator("seas", "lakes", "topology", "declared_world_bounds", mode="before")
    @classmethod
    def revalidate_sources(cls, value: object) -> object:
        if isinstance(value, (HydrologySeasPolicy, HydrologyLakesPolicy, WorldTopology, WorldBounds)):
            validate_immutable(value)
            return type(value).model_validate(value.model_dump(warnings=False), strict=True)
        return value

    @model_validator(mode="after")
    def complete_sources(self) -> Self:
        validate_immutable(self)
        if not self.z_min <= self.default_water_level <= self.z_max:
            raise ValueError("default water level outside world z bounds")
        if self.declared_world_bounds is not None:
            normalized = WorldTopology(mode=self.topology.mode, bounds=self.declared_world_bounds).bounds
            if normalized != self.topology.bounds:
                raise ValueError("declared world bounds do not match resolved topology")
        uids = tuple(source.value.source_uid if isinstance(source, ProceduralSource) else source.value.location_uid
                     for source in self.sources)
        if len(set(uids)) != len(uids):
            raise ValueError("duplicate water source UID")
        if len({anchor.source_uid for anchor in self.anchors}) != len(self.anchors):
            raise ValueError("duplicate water anchor UID")
        for source in self.sources:
            if source.value.liquid not in self.liquid_keys:
                raise ValueError("water source liquid is absent from captured material membership")
        return self
