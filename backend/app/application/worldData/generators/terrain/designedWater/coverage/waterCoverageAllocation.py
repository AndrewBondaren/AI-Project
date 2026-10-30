"""Terrain-owned coverage requests and admitted geometry → one shared allocation."""

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.designedWater.preparation.designUniverse import WaterDesignUniverse, invalid_water_design_input
from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.dataModel.hydrology.policy.proceduralSourceAdmission import ProceduralSourceAdmissions
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, WaterCoverageBudget
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.topology.fineTopology import fine_topology


class WaterCoverageAllocation:
    def requests(self, sources: ProceduralSourceAdmissions, regions: TerrainRegionPlan) -> tuple[BodyCoverageRequest, ...]:
        requests = []
        for binding in sources.sources:
            if sources.admission_for(binding.placement_identity).decision.state in (PolicyState.READY, PolicyState.WAITING_SUPPORT):
                region = regions.snapshot.region_for(binding.source.value.generation_region_uid)
                if region is None:
                    raise invalid_water_design_input("active source generation region is absent from captured terrain regions")
                requests.append(BodyCoverageRequest(source_uid=binding.source.value.source_uid,
                    generation_region_uid=region.region_uid, generation_area_fine2=region.generation_area_fine2,
                    target_fraction=binding.context.water_fraction))
        return tuple(requests)

    def allocate(self, universe: WaterDesignUniverse, pending_regions: set[EntityUid],
                 control: PlanBuildControl) -> WaterCoverageBudget | None:
        fine_bounds = fine_topology(universe.batch.topology, universe.grid.fine_span).bounds
        pending_sources = {intent.identity.source_uid for uid, intent in universe.by_region.items() if uid in pending_regions}
        if not universe.authored_sources.intersection(pending_sources) <= universe.geometry_by_source.keys():
            raise invalid_water_design_input("pending authored sources require captured geometry before budget")
        requests = tuple(request for request in universe.requests if request.source_uid in pending_sources)
        authored_coverages = []
        for geometry in universe.geometries:
            if geometry.pre_hydrology_ref != universe.pre_hydrology.ref:
                raise invalid_water_design_input("authored coverage must retain its captured terrain revision")
            if geometry.source_uid not in pending_sources:
                continue
            control.raise_if_shutdown()
            coverage = RegionCoverageMeasure.from_cells(
                frozenset(cell for footprint in geometry.footprints for cell in footprint),
                region_uid=geometry.source_uid, space=geometry.coordinate_space, grid=universe.grid)
            if any(not fine_bounds.contains(span.x0, span.y) or not fine_bounds.contains(span.x1 - 1, span.y)
                    for span in coverage.spans):
                raise invalid_water_design_input("authored coverage requires canonical native world geometry")
            authored_coverages.append(coverage)
        budget: WaterCoverageBudget | None = None
        if universe.regions.snapshot.world_region is not None:
            measure_uid = universe.regions.snapshot.world_region.region_uid
            authored_union = RegionCoverageMeasure.union(tuple(authored_coverages), region_uid=measure_uid)
            auto_union = RegionCoverageMeasure.union(tuple(universe.coverages[request.generation_region_uid]
                for request in requests), region_uid=measure_uid)
            available = RegionCoverageMeasure.subtract(auto_union, authored_union, region_uid=measure_uid)
            budget = WaterCoverageBudgetPolicy().calculate(universe.regions.snapshot.world_region, universe.world_context, requests,
                authored_union_fine2=RegionCoverageMeasure.area(authored_union),
                available_auto_area_fine2=RegionCoverageMeasure.area(available))
        return budget
