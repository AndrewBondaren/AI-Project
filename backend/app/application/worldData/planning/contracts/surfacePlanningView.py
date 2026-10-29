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
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput
from app.dataModel.terrain.regions.regionPlanningInput import TerrainRegionPlanningInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput, CoatingPlanInput
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.hydrology.sources.waterDesignSource import ProceduralSource


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


class GeoSurfacePlanningView(BaseModel):
    """Complete authored GEO source closure, before any provider computation."""

    model_config = ReadySurfacePlanningView.model_config

    kind: Literal[SurfacePlanningViewKind.READY] = SurfacePlanningViewKind.READY
    world_uid: EntityUid
    revision: StateViewRevision = Field(min_length=32, max_length=32)
    climate_base: ClimateBaseInput
    terrain_base: TerrainBaseInput
    region_input: TerrainRegionPlanningInput
    water_placement: GeoWaterPlacementInput
    relief: ReliefPlanInput
    hydrology: GeoHydrologyPlanInput
    river_relief: RiverReliefInput
    hydrology_final: HydrologyFinalInput
    climate_local: ClimateLocalInput
    boundary_input: CoastlineBoundaryInput
    surface_support: SurfaceSupportInput
    coating_input: CoatingPlanInput
    capture_diagnostics: tuple[PlanDiagnostic, ...]

    @model_validator(mode="after")
    def coherent_inputs(self) -> Self:
        validate_immutable(self)
        terrain, water, routes = self.terrain_base, self.water_placement, self.hydrology
        if self.climate_base.bbox != terrain.bbox or self.climate_base.fine_span != terrain.grid.fine_span:
            raise ValueError("GEO climate and terrain require one captured extent/scale")
        for grid in (water.grid, self.region_input.grid, self.relief.grid, routes.grid,
                     self.river_relief.grid, self.hydrology_final.grid, self.boundary_input.grid, self.surface_support.grid):
            if grid != terrain.grid:
                raise ValueError("GEO phases require one captured grid")
        for topology in (self.region_input.topology, routes.topology, self.river_relief.topology,
                         self.hydrology_final.topology, self.boundary_input.topology, self.surface_support.topology):
            if topology != water.topology:
                raise ValueError("GEO phases require one captured topology")
        bounds, bbox = water.topology.bounds, terrain.bbox
        if (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max) != (bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max):
            raise ValueError("GEO extent must match topology bounds")
        if self.region_input.declared_world_bounds != water.declared_world_bounds:
            raise ValueError("GEO phases must preserve authored world-bounds presence")
        for inputs in (water, self.relief, routes, self.river_relief):
            if (inputs.z_min, inputs.z_max) != (terrain.z_min, terrain.z_max):
                raise ValueError("GEO phases require one captured z range")
        for mode in (routes.resolution_mode, self.boundary_input.resolution_mode, self.coating_input.resolution_mode):
            if mode != water.resolution_mode:
                raise ValueError("GEO phases require one execution mode")
        if not water.enabled == routes.enabled == self.hydrology_final.enabled:
            raise ValueError("GEO phases require one captured root enabled value")
        if water.default_water_level != routes.default_water_level or water.liquid_keys != routes.liquid_keys:
            raise ValueError("GEO phases require the same water level and material membership")
        if water.seas != routes.seas or water.lakes != routes.lakes:
            raise ValueError("GEO phases require the same authored water category settings")
        if terrain.seed != routes.seed or terrain.seed != self.surface_support.seed:
            raise ValueError("GEO phases require one captured terrain seed")
        source_uids = {source.value.source_uid if isinstance(source, ProceduralSource) else source.value.location_uid
                       for source in water.sources}
        boundary_uids = {source.location_uid for source in self.boundary_input.sources}
        if source_uids & boundary_uids:
            raise ValueError("dependent boundaries cannot enter the body-producing source universe")
        return self


type GeoSurfacePlanningViewResult = Annotated[
    GeoSurfacePlanningView | NoExtentSurfacePlanningView, Field(discriminator="kind")]
