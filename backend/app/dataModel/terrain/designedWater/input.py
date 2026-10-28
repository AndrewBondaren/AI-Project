"""Resolved strategy boundary; validation only, without policy or spatial resolution."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.hydrology.sources.waterDesignSource import (
    AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource, WaterDesignSource,
)
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.identity.planKey import RegionPlanScope
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.dataModel.terrain.designedWater.draft import (
    AuthoredWaterDesignDraft, ProceduralWaterDesignDraft, WaterDesignDraft,
)
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.immutableValue import validate_immutable

_DRAFT = TypeAdapter(WaterDesignDraft)


class _WaterDesignInput(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    strategy: Strategy
    source: WaterDesignSource
    metadata: WaterSourceMetadata
    context: ResolvedWaterGenerationContext
    region: TerrainRegionExtent
    budget: BodyCoverageAllocation
    seed_root: EntityUid
    topology: WorldTopology
    grid: SurfaceGridSettings
    pre_hydrology: PlanEnvelope[TerrainPlan]
    region_coverage: RegionCoverage

    @property
    def pre_hydrology_ref(self) -> PlanRef:
        return self.pre_hydrology.ref

    @field_validator("topology", mode="before")
    @classmethod
    def revalidate_topology(cls, value: object) -> object:
        return value.model_dump(warnings=False) if isinstance(value, WorldTopology) else value

    @model_validator(mode="after")
    def coherent_inputs(self) -> Self:
        source, metadata = self.source, self.metadata
        value = source.value
        uid = source.value.source_uid if isinstance(source, ProceduralSource) else source.value.location_uid
        if uid != metadata.source_uid or source.kind != metadata.source_kind or value.liquid != metadata.liquid:
            raise ValueError("source and metadata identity/liquid mismatch")
        kind = BasinKind.LAKE if isinstance(source, AuthoredLakeSource) else source.value.kind
        if kind != metadata.body_kind:
            raise ValueError("source and metadata body kind mismatch")
        if isinstance(source, (AuthoredBasinSource, ProceduralSource)):
            if source.value.z_water_level is not None and source.value.z_water_level != metadata.level:
                raise ValueError("metadata must preserve explicit source water level")
        if self.context.strategy != self.strategy:
            raise ValueError("resolved context and effective strategy mismatch")
        if self.budget.source_uid != uid or self.budget.generation_region_uid != self.region.region_uid:
            raise ValueError("allocation identity mismatch")
        if isinstance(source, ProceduralSource) and source.value.generation_region_uid != self.region.region_uid:
            raise ValueError("procedural region binding mismatch")
        if self.region_coverage.region_uid != self.region.region_uid:
            raise ValueError("coverage identity mismatch")
        if sum(s.x1 - s.x0 for s in self.region_coverage.spans) != self.region.generation_area_fine2:
            raise ValueError("coverage area mismatch")
        if self.budget.requested_fine2 > self.region.generation_area_fine2:
            raise ValueError("request exceeds generation area")
        fine_bounds = fine_topology(self.topology, self.grid.fine_span).bounds
        if any(not fine_bounds.contains(s.x0, s.y) or not fine_bounds.contains(s.x1 - 1, s.y)
               for s in self.region_coverage.spans):
            raise ValueError("coverage must use canonical world fine coordinates")
        bounds, bbox = self.topology.bounds, self.pre_hydrology.payload.bbox
        if (bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max) != (
                bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max):
            raise ValueError("pre-hydrology surface must match the coarse topology")
        key = self.pre_hydrology_ref.key
        if isinstance(key.scope, RegionPlanScope) and key.scope.region_uid != self.region.region_uid:
            raise ValueError("pre-hydrology ref belongs to another region")
        if any(d.ref.key.world_uid != key.world_uid for d in self.pre_hydrology.dependencies):
            raise ValueError("pre-hydrology dependencies belong to another world")
        if isinstance(self, (NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput)):
            if self.field_policy.seed_root != self.seed_root or self.field_policy.topology != fine_topology(self.topology, self.grid.fine_span):
                raise ValueError("recipe must match seed and world fine topology")
        validate_immutable(self)
        return self

    def validate_draft(self, draft: WaterDesignDraft) -> WaterDesignDraft:
        """Check a returned draft against this input without preparing any candidates."""
        draft = _DRAFT.validate_python(draft, strict=True)
        if draft.metadata != self.metadata:
            raise ValueError("draft metadata differs from input")
        if isinstance(self, AuthoredWaterDesignInput):
            if not isinstance(draft, AuthoredWaterDesignDraft):
                raise ValueError("authored strategy requires authored geometry")
            if isinstance(self.source, AuthoredBasinSource) and draft.floor_z != self.source.value.floor_z:
                raise ValueError("authored basin floor must be preserved")
            topology = self.topology if draft.coordinate_space is CoordinateSpace.WORLD_SURFACE_GRID else fine_topology(self.topology, self.grid.fine_span)
            if any(topology.canonicalize(*c) != c for footprint in draft.footprints for c in footprint):
                raise ValueError("authored footprint contains noncanonical coordinates")
        elif isinstance(self, (NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput)):
            if not isinstance(draft, ProceduralWaterDesignDraft) or draft.field.recipe != self.field_policy:
                raise ValueError("procedural draft must preserve the input recipe")
            coords = tuple(c for c, _ in draft.field.samples)
            if coords != tuple(c for c, _ in self.pre_hydrology.payload.surface_z):
                raise ValueError("field requires one sample per canonical coarse working cell")
        if isinstance(draft.floor_profile, FieldFloorProfile):
            recipe = draft.floor_profile.recipe
            if recipe.seed_root != self.seed_root or recipe.topology != fine_topology(self.topology, self.grid.fine_span):
                raise ValueError("floor recipe differs from input world")
        validate_immutable(draft)
        return draft


class AuthoredWaterDesignInput(_WaterDesignInput, frozen=True):
    strategy: Literal[Strategy.AUTHORED_REGION] = Strategy.AUTHORED_REGION
    source: Annotated[AuthoredBasinSource | AuthoredLakeSource | CoastlineWaterSource, Field(discriminator="kind")]


class NoiseWaterDesignInput(_WaterDesignInput, frozen=True):
    strategy: Literal[Strategy.CONTINENTAL_NOISE] = Strategy.CONTINENTAL_NOISE
    source: ProceduralSource
    field_policy: NoiseRecipe


class PlateWaterDesignInput(_WaterDesignInput, frozen=True):
    strategy: Literal[Strategy.PLATE] = Strategy.PLATE
    source: ProceduralSource
    field_policy: PlateRecipe


class PlateNoiseWaterDesignInput(_WaterDesignInput, frozen=True):
    strategy: Literal[Strategy.PLATE_NOISE] = Strategy.PLATE_NOISE
    source: ProceduralSource
    field_policy: PlateNoiseRecipe


type WaterDesignInput = Annotated[
    AuthoredWaterDesignInput | NoiseWaterDesignInput | PlateWaterDesignInput | PlateNoiseWaterDesignInput,
    Field(discriminator="strategy"),
]
