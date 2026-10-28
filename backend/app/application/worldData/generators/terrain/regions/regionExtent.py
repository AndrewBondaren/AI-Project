"""One pre-water region measurement; no surface reads, writes or water policy (GEO-1 §6.3)."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.application.worldData.generators.terrain.regions.shapeCoverage import coverage_for_shape
from app.application.worldData.masks.regionRasterContext import RasterWorld
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape, EllipseShape
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.regionPlanningInput import TerrainRegionPlanningInput
from app.dataModel.terrain.regions.terrainRegionExtent import RegionExtentIssueCode, TerrainRegionExtent
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan, TerrainRegionsSnapshot
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.ids import seed_root


def _failure(code: RegionExtentIssueCode, region_uid: EntityUid, message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("terrain_regions", region_uid), message, code=code.value),))


def require_terrain_region(snapshot: TerrainRegionsSnapshot, *, world_uid: EntityUid,
                           snapshot_uid: EntityUid, region_uid: EntityUid) -> TerrainRegionExtent:
    snapshot = TerrainRegionsSnapshot.model_validate(snapshot, strict=True)
    if snapshot.world_uid != world_uid or snapshot.snapshot_uid != snapshot_uid:
        raise _failure(RegionExtentIssueCode.IDENTITY_MISMATCH, region_uid, "region snapshot identity mismatch")
    region = snapshot.region_for(region_uid)
    if region is None:
        raise _failure(RegionExtentIssueCode.MISSING_REGION, region_uid, "required generation region is unavailable")
    return region


def prepare_terrain_regions(world: RasterWorld, *, snapshot_uid: EntityUid, world_region_uid: EntityUid,
                            inputs: TerrainRegionPlanningInput) -> TerrainRegionPlan:
    inputs = TerrainRegionPlanningInput.model_validate(inputs, strict=True)
    topology = fine_topology(inputs.topology, inputs.grid.fine_span)
    root = seed_root(world)
    coverages: list[RegionCoverage] = []
    world_region: TerrainRegionExtent | None = None
    regions: list[TerrainRegionExtent] = []
    if inputs.declared_world_bounds is not None:
        bounds = topology.bounds
        coverage = coverage_for_shape(BboxShape(x_min=bounds.x_min, x_max=bounds.x_max,
            y_min=bounds.y_min, y_max=bounds.y_max), root=root, region_uid=world_region_uid, topology=topology)
        coverages.append(coverage)
        world_region = TerrainRegionExtent(region_uid=world_region_uid,
            generation_area_fine2=RegionCoverageMeasure.area(coverage))
    anchors = {a.source_uid: a.position for a in inputs.anchors}
    for entry in sorted(inputs.regions, key=lambda r: r.region_uid):
        if world_region is not None and entry.region_uid == world_region_uid:
            raise _failure(RegionExtentIssueCode.INVALID_GEOMETRY, entry.region_uid, "region duplicates world region UID")
        if entry.owner_ref is not None and entry.owner_ref.key.world_uid != world.world_uid:
            raise _failure(RegionExtentIssueCode.IDENTITY_MISMATCH, entry.region_uid, "region owner ref belongs to another world")
        geometry = entry.geometry
        if isinstance(geometry, RegionCoverage):
            if any(s.y < topology.bounds.y_min or s.y > topology.bounds.y_max or
                   s.x0 < topology.bounds.x_min or s.x1 > topology.bounds.x_max + 1 for s in geometry.spans):
                raise _failure(RegionExtentIssueCode.INVALID_GEOMETRY, entry.region_uid, "claim spans are not canonical fine cells")
            coverage = geometry
        else:
            if isinstance(geometry, AnchorRadiusShape):
                anchor = anchors.get(geometry.anchor_uid)
                if anchor is None:
                    raise _failure(RegionExtentIssueCode.MISSING_ANCHOR, entry.region_uid, "required region anchor is unavailable")
                geometry = EllipseShape(cx=anchor[0], cy=anchor[1], rx=geometry.radius,
                                        ry=geometry.radius, edge_noise=geometry.edge_noise)
            coverage = coverage_for_shape(geometry, root=root, region_uid=entry.region_uid, topology=topology)
        coverages.append(coverage)
        regions.append(TerrainRegionExtent(region_uid=entry.region_uid,
            generation_area_fine2=RegionCoverageMeasure.area(coverage)))
    snapshot = TerrainRegionsSnapshot(world_uid=world.world_uid, snapshot_uid=snapshot_uid,
                                      world_region=world_region, regions=tuple(regions))
    return TerrainRegionPlan(snapshot=snapshot, coverages=tuple(coverages))
