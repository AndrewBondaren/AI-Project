"""Immutable captured source projections for the typed surface planning entry."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput, HydrologyPlanInput
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.planning.identity.planKey import StateViewRevision
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput


class SurfacePlanningViewKind(StrEnum):
    READY = "ready"
    NO_EXTENT = "no_extent"


class ReadySurfacePlanningView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[SurfacePlanningViewKind.READY] = SurfacePlanningViewKind.READY
    world_uid: EntityUid
    revision: StateViewRevision = Field(min_length=32, max_length=32)
    climate_base: ClimateBaseInput
    terrain_base: TerrainBaseInput
    water_placement: WaterPlacementInput
    relief: ReliefPlanInput
    hydrology: HydrologyPlanInput
    climate_local: ClimateLocalInput
    river_relief: RiverReliefInput
    hydrology_final: HydrologyFinalInput
    capture_diagnostics: tuple[PlanDiagnostic, ...]

    @model_validator(mode="after")
    def coherent_inputs(self) -> Self:
        terrain, water, routes = self.terrain_base, self.water_placement, self.hydrology
        if self.climate_base.bbox != terrain.bbox or self.climate_base.fine_span != terrain.grid.fine_span:
            raise ValueError("climate and terrain must use the same captured extent/scale")
        for grid in (water.grid, self.relief.grid, routes.grid, self.river_relief.grid, self.hydrology_final.grid):
            if grid != terrain.grid:
                raise ValueError("surface phases require one captured grid")
        for topology in (routes.topology, self.river_relief.topology, self.hydrology_final.topology):
            if topology != water.topology:
                raise ValueError("surface phases require one captured topology")
        bounds, bbox = water.topology.bounds, terrain.bbox
        if (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max) != (bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max):
            raise ValueError("surface extent must match topology bounds")
        if water.resolution_mode != routes.resolution_mode or not water.enabled == routes.enabled == self.hydrology_final.enabled:
            raise ValueError("surface hydrology phases require the same captured execution policy")
        return self


class NoExtentSurfacePlanningView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[SurfacePlanningViewKind.NO_EXTENT] = SurfacePlanningViewKind.NO_EXTENT
    world_uid: EntityUid
    revision: StateViewRevision = Field(min_length=32, max_length=32)
    capture_diagnostics: tuple[PlanDiagnostic, ...]


type SurfacePlanningView = Annotated[
    ReadySurfacePlanningView | NoExtentSurfacePlanningView, Field(discriminator="kind")]
