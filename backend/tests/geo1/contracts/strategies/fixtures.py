"""Small coherent world; scale differs from both coordinate axes and light side."""

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.hydrology.sources.proceduralWaterSource import ProceduralWaterSource
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, ProceduralSource
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.dataModel.terrain.designedWater.draft import AuthoredWaterDesignDraft, ProceduralWaterDesignDraft
from app.dataModel.terrain.designedWater.fields.field import ContinentalField, NoiseRecipe, PlateRecipe, PlateNoiseRecipe
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


def inputs(strategy=Strategy.CONTINENTAL_NOISE):
    topology = WorldTopology(mode=WorldTopologyMode.WRAPPED, bounds=WorldBounds(x_min=-1, x_max=0, y_min=1, y_max=1))
    grid = SurfaceGridSettings(fine_span=4, light_side=2)
    source = (AuthoredBasinSource(value=DeclaredBasin(location_uid="source", kind=BasinKind.SEA,
        footprint=BboxShape(x_min=-4, x_max=-1, y_min=4, y_max=7), floor_z=-5))
        if strategy is Strategy.AUTHORED_REGION else ProceduralSource(value=ProceduralWaterSource(
            source_uid="source", generation_region_uid="region", kind=BasinKind.SEA, liquid="water")))
    ref = PlanRef(key=PlanKey(world_uid="world", scope=WorldPlanScope(), contract_id="terrain_base",
        schema_version=1, algorithm_version=1, input_fingerprint=b"i" * 32), output_fingerprint=b"o" * 32)
    raw = dict(strategy=strategy, source=source, metadata=WaterSourceMetadata(source_uid="source",
        source_kind=source.kind, body_kind=BasinKind.SEA, liquid="water", level=0,
        bands=HydrologyBands(min=1, max=2), source_path=("bodies", 0), default_depth=5),
        context=ResolvedWaterGenerationContext(level=WaterGenerationScope.WATER_BODY,
            provenance=tuple((name, (WaterGenerationScope.WATER_BODY, name)) for name in ("autoresolve", "strategy", "water_fraction")),
            water_fraction=0.5, autoresolve=False, strategy=strategy),
        region=TerrainRegionExtent(region_uid="region", generation_area_fine2=16),
        budget=BodyCoverageAllocation(source_uid="source", generation_region_uid="region", requested_fine2=8, allocated_fine2=6),
        seed_root="seed", topology=topology, grid=grid,
        pre_hydrology=PlanEnvelope[TerrainPlan](ref=ref, dependencies=(), diagnostics=(), payload=TerrainPlan(
            bbox=GridBBox(-1, 0, 1, 1), surface_z=((SurfaceGridCoord(-1, 1), 3), (SurfaceGridCoord(0, 1), 5)))),
        region_coverage=RegionCoverage(region_uid="region", spans=tuple(CoverageSpan(y=y, x0=-4, x1=0) for y in range(4, 8))))
    if strategy is Strategy.AUTHORED_REGION:
        return AuthoredWaterDesignInput(**raw, geometry=AuthoredWaterGeometry(source_uid="source",
            pre_hydrology_ref=ref, coordinate_space=CoordinateSpace.WORLD_FINE_GRID,
            footprints=(frozenset({(-4, 4), (-3, 4)}),), rim_level=None, z_min=-20, notices=()))
    raw["z_min"] = -20
    common = dict(seed_root="seed", topology=fine_topology(topology, grid.fine_span))
    if strategy is Strategy.CONTINENTAL_NOISE:
        return NoiseWaterDesignInput(**raw, field_policy=NoiseRecipe(**common, noise_policy=ContinentalNoisePolicy()))
    if strategy is Strategy.PLATE:
        return PlateWaterDesignInput(**raw, field_policy=PlateRecipe(**common, plate_policy=PlateGenerationPolicy()))
    return PlateNoiseWaterDesignInput(**raw, field_policy=PlateNoiseRecipe(**common,
        plate_policy=PlateGenerationPolicy(), noise_policy=ContinentalNoisePolicy(), composition_policy=FieldCompositionPolicy()))


def draft_for(input):
    if isinstance(input, AuthoredWaterDesignInput):
        return AuthoredWaterDesignDraft(metadata=input.metadata, floor_z=-5, floor_profile=None,
            coordinate_space=CoordinateSpace.WORLD_FINE_GRID, footprints=(frozenset({(-4, 4), (-3, 4)}),))
    return ProceduralWaterDesignDraft(metadata=input.metadata, floor_z=-5,
        field=ContinentalField(recipe=input.field_policy, samples=tuple((c, -0.25) for c, _ in input.pre_hydrology.payload.surface_z)),
        floor_profile=FieldFloorProfile(recipe=input.field_policy, level=0, depth=5, z_min=-20))
