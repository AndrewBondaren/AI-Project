"""Captured join with actual common cascade/policy decisions; no geometry before admission."""
from dataclasses import dataclass, replace

from app.application.worldData.generators.terrain.designedWater.preparation.coastlineWaterSourceAdapter import CoastlineWaterSourceAdapter
from app.dataModel.cascade.runtimeContext import freeze_resolved_context
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldHydrologyGenerationFields, WorldWaterGenerationSettings
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.placement.intent import PlacementIdentity, PlacementIntent
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.common import PlacementMode
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe, WaterFieldRecipe
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometryRequest
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage, CoverageSpan
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.authored.fixtures import request
from tests.geo1.authored.test_geometry import ring
from tests.geo1.contracts.strategies.fixtures import draft_for
from tests.geo1.contracts.test_hydrology_generation import context_for, resolve as resolve_generation
from tests.geo1.placement_policy.fixtures import bind, execute


@dataclass(frozen=True)
class Capture:
    source: DeclaredCoastline
    geometry_request: AuthoredWaterGeometryRequest
    context: ResolvedWaterGenerationContext
    generation: HydrologyGenerationDecision
    region: TerrainRegionExtent
    budget: BodyCoverageAllocation
    region_coverage: RegionCoverage
    metadata: WaterSourceMetadata
    admission: PlacementAdmissionInput
    field_policy: WaterFieldRecipe | None


def capture(*, strategy=Strategy.CONTINENTAL_NOISE, closed=False, auto=True, priority=None,
            mode=WorldTopologyMode.PLANAR, resolution=ResolutionMode.VALIDATE_ONLY):
    source = DeclaredCoastline(location_uid="source", kind=BasinKind.SEA, closed=closed,
        water_side=WaterSide.INTERIOR if closed else None, path=ring() if closed else ring()[:2],
        placement_specificity=priority)
    req = request(CoastlineWaterSource(value=source), mode=mode)
    root = WorldHydrologyGenerationFields(generation=WorldWaterGenerationSettings(
        autoresolve=auto, strategy=strategy, water_fraction=0.5))
    working = context_for(root)
    context = freeze_resolved_context(working, ResolvedWaterGenerationContext)
    generation = resolve_generation(root,working,resolution)
    decision = execute(bind(CoastlineWaterSource(value=source),strategy=strategy), resolution)
    header = PlacementHeader(identity=PlacementIdentity(world_uid="world",source_uid="source",region_uid="water-region"),
        mode=PlacementMode.ABSOLUTE, dependencies=(),permitted_overlaps=(),separations=())
    metadata = WaterSourceMetadata(source_uid="source",source_kind=req.source.kind,
        body_kind=source.kind,liquid=source.liquid,level=0,bands=req.seas.bands,
        source_path=("hydrology","declared_coastlines",0),default_depth=5)
    grid,bounds = req.grid,req.topology.bounds
    extent = TerrainRegionExtent(region_uid="region",generation_area_fine2=bounds.width*bounds.height*grid.fine_span**2)
    coverage = RegionCoverage(region_uid="region",spans=tuple(CoverageSpan(y=y,x0=bounds.x_min*grid.fine_span,
        x1=(bounds.x_max+1)*grid.fine_span) for y in range(bounds.y_min*grid.fine_span,(bounds.y_max+1)*grid.fine_span)))
    recipe = None
    if strategy is Strategy.CONTINENTAL_NOISE:
        recipe = NoiseRecipe(seed_root=req.seed_root,topology=fine_topology(req.topology,grid.fine_span),noise_policy=ContinentalNoisePolicy())
    elif strategy is Strategy.PLATE:
        recipe = PlateRecipe(seed_root=req.seed_root,topology=fine_topology(req.topology,grid.fine_span),plate_policy=PlateGenerationPolicy())
    elif strategy is Strategy.PLATE_NOISE:
        recipe = PlateNoiseRecipe(seed_root=req.seed_root,topology=fine_topology(req.topology,grid.fine_span),
            plate_policy=PlateGenerationPolicy(),noise_policy=ContinentalNoisePolicy(),composition_policy=FieldCompositionPolicy())
    return Capture(source,req,context,generation,extent,
        BodyCoverageAllocation(source_uid="source",generation_region_uid="region",requested_fine2=extent.generation_area_fine2,allocated_fine2=36),
        coverage,metadata,PlacementAdmissionInput(header=header,decision=decision),recipe)


def prepare(value):
    return CoastlineWaterSourceAdapter().prepare_source(value.source,geometry_request=value.geometry_request,
        context=value.context,generation=value.generation,region=value.region,budget=value.budget,
        region_coverage=value.region_coverage,metadata=value.metadata,admission=value.admission,field_policy=value.field_policy)


def intent(header):
    return PlacementIntent(identity=header.identity,mode=header.mode,shape=None,dependencies=header.dependencies,
        permitted_overlaps=header.permitted_overlaps,separations=header.separations)
