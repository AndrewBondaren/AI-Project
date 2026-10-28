"""Complete coarse terrain and fine authored declarations for G5."""

from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, AuthoredLakeSource
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometryRequest
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


def request(source=None, *, seas=None, anchors=(), z_min=-20, seed="authored-seed", mode=WorldTopologyMode.PLANAR):
    if source is None:
        source = AuthoredBasinSource(value=DeclaredBasin(location_uid="source", kind=BasinKind.SEA,
            footprint=BboxShape(x_min=4, x_max=12, y_min=4, y_max=12), floor_z=-5))
    topology = WorldTopology(mode=mode, bounds=WorldBounds(x_min=0, x_max=9, y_min=0, y_max=8))
    ref = PlanRef(key=PlanKey(world_uid="world", scope=WorldPlanScope(), contract_id="terrain_base",
        schema_version=1, algorithm_version=1, input_fingerprint=b"i" * 32), output_fingerprint=b"o" * 32)
    terrain = TerrainPlan(bbox=GridBBox(0, 9, 0, 8), surface_z=tuple((SurfaceGridCoord(x, y),
        12 if (x, y) == (2, 3) else 10) for y in range(9) for x in range(10)))
    return AuthoredWaterGeometryRequest(source=source,
        pre_hydrology=PlanEnvelope[TerrainPlan](ref=ref, payload=terrain, dependencies=(), diagnostics=()),
        topology=topology, grid=SurfaceGridSettings(fine_span=2, light_side=3), seed_root=seed,
        anchors=anchors, seas=seas if seas is not None else HydrologySeasPolicy(), z_min=z_min)


def design_input(req, geometry=None):
    if geometry is None:
        geometry = prepare_authored_water_geometry(req)
    lake = isinstance(req.source, AuthoredLakeSource)
    uid = req.source.value.location_uid
    metadata = WaterSourceMetadata(source_uid=uid, source_kind=req.source.kind,
        body_kind=BasinKind.LAKE if lake else req.source.value.kind, liquid=req.source.value.liquid,
        level=geometry.rim_level if lake else 0, bands=HydrologyBands(min=1, max=2),
        source_path=("sources", uid), default_depth=5)
    coverage = RegionCoverage(region_uid="region", spans=tuple(CoverageSpan(y=y, x0=0, x1=20) for y in range(18)))
    return AuthoredWaterDesignInput(source=req.source, metadata=metadata, geometry=geometry,
        context=ResolvedWaterGenerationContext(level=Scope.WATER_BODY,
            provenance=tuple((n, (Scope.WATER_BODY, n)) for n in ("autoresolve", "strategy", "water_fraction")),
            water_fraction=0.6, autoresolve=False, strategy=Strategy.AUTHORED_REGION),
        region=TerrainRegionExtent(region_uid="region", generation_area_fine2=360), region_coverage=coverage,
        budget=BodyCoverageAllocation(source_uid=uid, generation_region_uid="region", requested_fine2=0, allocated_fine2=0),
        seed_root=req.seed_root, topology=req.topology, grid=req.grid, pre_hydrology=req.pre_hydrology)
