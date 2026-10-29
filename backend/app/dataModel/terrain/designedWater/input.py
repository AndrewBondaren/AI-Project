"""Resolved strategy boundary; validation only, without policy or spatial resolution."""

from typing import Annotated, Generic, Literal, Self
from typing_extensions import TypeVar

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
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.dataModel.terrain.designedWater.draft import (
    AuthoredWaterDesignDraft, ProceduralWaterDesignDraft, WaterDesignDraft,
)
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe
from app.dataModel.terrain.designedWater.geometry.waterDesignConstraints import WaterDesignConstraints
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry, AuthoredWaterSource
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.immutableValue import validate_immutable

_DRAFT = TypeAdapter(WaterDesignDraft)

# Source identity and strategy are independent axes. Defaults preserve the full
# allowed source union at unspecialized call sites, never an implicit Any.
type ProceduralWaterDesignSource = Annotated[ProceduralSource | CoastlineWaterSource, Field(discriminator="kind")]
SourceT = TypeVar("SourceT", bound=WaterDesignSource, default=WaterDesignSource, covariant=True)
AuthoredSourceT = TypeVar("AuthoredSourceT", bound=AuthoredWaterSource, default=AuthoredWaterSource, covariant=True)
ProceduralSourceT = TypeVar("ProceduralSourceT", bound=ProceduralWaterDesignSource,
                            default=ProceduralWaterDesignSource, covariant=True)


class WaterDesignInput(BaseModel, Generic[SourceT], frozen=True):
    """Common ready inputs, preserving the caller's exact source type.

    Consumers dispatch through WaterStrategyInput, whose concrete variants also
    validate source compatibility at runtime; TypeVar bounds alone are static.
    """
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    strategy: Strategy
    source: Annotated[SourceT, Field(discriminator="kind")]
    metadata: WaterSourceMetadata
    context: ResolvedWaterGenerationContext
    region: TerrainRegionExtent
    budget: BodyCoverageAllocation
    seed_root: EntityUid
    topology: WorldTopology
    grid: SurfaceGridSettings
    pre_hydrology: PlanEnvelope[TerrainPlan]
    region_coverage: RegionCoverage
    constraints: WaterDesignConstraints | None = None

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
        if not isinstance(source, (AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource)):
            raise ValueError("water input requires a supported typed water source")
        # Runtime validation remains authoritative even if callers explicitly
        # parameterize a generic with a source outside its static bound.
        if isinstance(self, AuthoredWaterDesignInput):
            if not isinstance(source, (AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource)):
                raise ValueError("authored strategy requires an authored water source")
        elif isinstance(self, (NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput)):
            if not isinstance(source, (ProceduralSource, CoastlineWaterSource)):
                raise ValueError("procedural strategy requires a procedural or coastline water source")
        constraints = self.constraints
        if isinstance(self, AuthoredWaterDesignInput) and constraints is not None:
            raise ValueError("authored input already carries its geometry")
        if isinstance(self, (NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput)) and isinstance(source, CoastlineWaterSource) and constraints is None:
            raise ValueError("procedural coastline requires captured terrain constraints")
        if constraints is not None:
            if constraints.source != source or constraints.pre_hydrology_ref != self.pre_hydrology_ref or constraints.grid != self.grid:
                raise ValueError("constraints must match full source, terrain revision and grid")
            if any(self.topology.canonicalize(*cell) != cell for cell in constraints.allowed_cells):
                raise ValueError("constraints require canonical coarse coordinates")
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
            if (draft.coordinate_space != self.geometry.coordinate_space or
                    frozenset(c for part in draft.footprints for c in part) !=
                    frozenset(c for part in self.geometry.footprints for c in part)):
                raise ValueError("authored draft must preserve the prepared source geometry")
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
            if isinstance(self, (NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput)) and (
                    draft.floor_profile.z_min != self.z_min or draft.floor_profile.depth != self.metadata.default_depth):
                raise ValueError("procedural floor must preserve captured world z_min and metadata depth")
        validate_immutable(draft)
        return draft


class AuthoredWaterDesignInput(WaterDesignInput[AuthoredSourceT], Generic[AuthoredSourceT], frozen=True):
    strategy: Literal[Strategy.AUTHORED_REGION] = Strategy.AUTHORED_REGION
    # G5 geometry was computed once before metadata (lake rim level depends on
    # its footprint). G8 binds this immutable result; strategy never rerasterizes.
    geometry: AuthoredWaterGeometry

    @model_validator(mode="after")
    def coherent_authored_geometry(self) -> Self:
        geometry = self.geometry
        if geometry.source_uid != self.metadata.source_uid or geometry.pre_hydrology_ref != self.pre_hydrology_ref:
            raise ValueError("authored geometry must match source and terrain revision")
        topology = self.topology if geometry.coordinate_space is CoordinateSpace.WORLD_SURFACE_GRID else fine_topology(self.topology, self.grid.fine_span)
        if any(topology.canonicalize(*c) != c for part in geometry.footprints for c in part):
            raise ValueError("authored geometry coordinates must be canonical")
        if isinstance(self.source, AuthoredLakeSource):
            if geometry.rim_level != self.metadata.level:
                raise ValueError("lake metadata must use the computed geometry rim level")
        elif geometry.rim_level is not None:
            raise ValueError("only lake geometry carries a rim level")
        return self


class _ProceduralWaterDesignInput(WaterDesignInput[ProceduralSourceT], Generic[ProceduralSourceT], frozen=True):
    """Actual world lower bound for procedural floor profiles; never a terrain minimum."""

    z_min: Annotated[FineZ, Field(strict=True)]

    @model_validator(mode="after")
    def possible_floor(self) -> Self:
        if self.metadata.level <= self.z_min:
            raise ValueError("procedural water requires level > world z_min")
        if any(z < self.z_min for _, z in self.pre_hydrology.payload.surface_z):
            raise ValueError("pre-hydrology terrain lies below world z_min")
        return self


class NoiseWaterDesignInput(_ProceduralWaterDesignInput[ProceduralSourceT], Generic[ProceduralSourceT], frozen=True):
    strategy: Literal[Strategy.CONTINENTAL_NOISE] = Strategy.CONTINENTAL_NOISE
    field_policy: NoiseRecipe


class PlateWaterDesignInput(_ProceduralWaterDesignInput[ProceduralSourceT], Generic[ProceduralSourceT], frozen=True):
    strategy: Literal[Strategy.PLATE] = Strategy.PLATE
    field_policy: PlateRecipe


class PlateNoiseWaterDesignInput(_ProceduralWaterDesignInput[ProceduralSourceT], Generic[ProceduralSourceT], frozen=True):
    strategy: Literal[Strategy.PLATE_NOISE] = Strategy.PLATE_NOISE
    field_policy: PlateNoiseRecipe


# One closed strategy transport for validation and dispatch. Specialized inputs
# enter this same union; there is no second serialization or execution path.
type WaterStrategyInput = Annotated[
    AuthoredWaterDesignInput | NoiseWaterDesignInput | PlateWaterDesignInput | PlateNoiseWaterDesignInput,
    Field(discriminator="strategy"),
]


# A source-specific view of the same strategy transport, retaining exact source type.
type CoastlineWaterDesignInput = Annotated[
    AuthoredWaterDesignInput[CoastlineWaterSource] | NoiseWaterDesignInput[CoastlineWaterSource] |
    PlateWaterDesignInput[CoastlineWaterSource] | PlateNoiseWaterDesignInput[CoastlineWaterSource],
    Field(discriminator="strategy"),
]
