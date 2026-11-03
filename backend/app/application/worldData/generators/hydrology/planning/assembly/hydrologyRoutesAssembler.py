"""Order public hydrology operations and assemble their immutable results."""

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.application.worldData.generators.hydrology.load.paint.declaredWaterPaintProjector import DeclaredWaterPaintProjector
from app.application.worldData.generators.terrain.planning.projection.coarseSurface import TerrainProjectionPlanner
from app.application.worldData.generators.hydrology.planning.assembly.nativeRoutesPublication import NativeRoutesPublicationJob
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyRoutesPlan, GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan, FineWaterResult
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan, GeoWaterPlacementPlan
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan


class HydrologyRoutesAssembler:
    def __init__(self, water: WaterBodyPlanner, coarse: CoarseRiverPlanner,
                 fine: FineRiverPlanner, paint: DeclaredWaterPaintProjector,
                 terrain: TerrainProjectionPlanner | None = None) -> None:
        self._water, self._coarse, self._fine, self._paint = water, coarse, fine, paint
        self._terrain = terrain if terrain is not None else TerrainProjectionPlanner()

    def assemble_fine(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                      water: PlanEnvelope[FineWaterResult], expected_water: PlanRef,
                      # GEO-LEGACY-49: Bind route inputs to the same P2 publication.
                      specs: tuple[BasinSpec, ...],
                      classification_decisions: tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...],
                      control: PlanBuildControl) -> PlanEnvelope[GeoHydrologyRoutesPlan]:
        """Native route-stage entry; registration cutover remains a separate G10-A action."""
        control.raise_if_shutdown()
        projected = self._water.project_fine(water, expected_water=expected_water, world_uid=world_uid,
            inputs=inputs, specs=specs, classification_decisions=classification_decisions, control=control)
        surface = self._terrain.project_coarse(water.payload[0], topology=inputs.topology,
                                               grid=inputs.grid, control=control)
        coarse = self._coarse.plan(world_uid=world_uid, inputs=inputs,
            surface_z=surface.surface_z, water=projected.payload, control=control)
        control.raise_if_shutdown()
        fine = self._fine.refine_fine(world_uid=world_uid, inputs=inputs, water=water.payload,
                                      coarse=coarse.payload, control=control)
        control.raise_if_shutdown()
        paint = self._paint.project(rivers=inputs.declared_rivers, coastlines=inputs.coastlines,
            lakes=inputs.declared_lakes, anchors=inputs.anchors)
        payload = GeoHydrologyRoutesPlan(base=HydrologyRoutesPlan(
            coarse_open_water=projected.payload.coarse_open_water, water_bodies=projected.payload.water_bodies,
            physical_unions=projected.payload.physical_unions, coarse_routes=coarse.payload.routes,
            fine_routes=fine.payload.routes, fine_base_surface_z=fine.payload.base_surface_z,
            declared_paint=paint.payload), source_mapping=projected.payload.source_mapping,
            classification_decisions=classification_decisions)
        diagnostics = tuple(dict.fromkeys((*projected.diagnostics, *coarse.diagnostics,
                                           *fine.diagnostics, *paint.diagnostics)))
        return NativeRoutesPublicationJob().publish(
            PlanBuildResult[GeoHydrologyRoutesPlan](payload=payload, diagnostics=diagnostics),
            world_uid=world_uid, inputs=inputs, water=water.ref, control=control)

    # GEO-LEGACY-27: Retire the coarse assembly path.
    def assemble(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput,
                 relief: ReliefPlan, placement: WaterPlacementPlan,
                 control: PlanBuildControl) -> PlanBuildResult[HydrologyRoutesPlan]:
        control.raise_if_shutdown()
        water = self._water.plan(world_uid=world_uid, inputs=inputs,
            surface_z=relief.surface_z, placement=placement, control=control)
        return self._routes(world_uid=world_uid, inputs=inputs, relief=relief, water=water, control=control)

    # GEO-LEGACY-27: Retire the coarse assembly path.
    def assemble_geo(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                     relief: ReliefPlan, placement: GeoWaterPlacementPlan,
                     classification_decisions: tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...],
                     control: PlanBuildControl) -> PlanBuildResult[GeoHydrologyRoutesPlan]:
        control.raise_if_shutdown()
        water = self._water.plan_geo(world_uid=world_uid, inputs=inputs,
            surface_z=relief.surface_z, placement=placement,
            classification_decisions=classification_decisions, control=control)
        routes = self._routes(world_uid=world_uid, inputs=inputs, relief=relief, water=water, control=control)
        return PlanBuildResult[GeoHydrologyRoutesPlan](payload=GeoHydrologyRoutesPlan(
            base=routes.payload, source_mapping=water.payload.source_mapping,
            classification_decisions=classification_decisions), diagnostics=routes.diagnostics)

    # GEO-LEGACY-27: Retire the coarse assembly path.
    def _routes(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput | GeoHydrologyPlanInput,
                relief: ReliefPlan, water: PlanBuildResult[OpenWaterPlan],
                control: PlanBuildControl) -> PlanBuildResult[HydrologyRoutesPlan]:
        control.raise_if_shutdown()
        coarse = self._coarse.plan(world_uid=world_uid, inputs=inputs,
            surface_z=relief.surface_z, water=water.payload, control=control)
        control.raise_if_shutdown()
        fine = self._fine.plan(world_uid=world_uid, inputs=inputs,
            surface_z=relief.surface_z, water=water.payload, coarse=coarse.payload, control=control)
        control.raise_if_shutdown()
        paint = self._paint.project(rivers=inputs.declared_rivers, coastlines=inputs.coastlines,
            lakes=inputs.declared_lakes, anchors=inputs.anchors)
        control.raise_if_shutdown()
        return PlanBuildResult[HydrologyRoutesPlan](payload=HydrologyRoutesPlan(
            coarse_open_water=water.payload.coarse_open_water, water_bodies=water.payload.water_bodies,
            physical_unions=water.payload.physical_unions, coarse_routes=coarse.payload.routes,
            fine_routes=fine.payload.routes, fine_base_surface_z=fine.payload.base_surface_z,
            declared_paint=paint.payload), diagnostics=tuple(dict.fromkeys(
                (*water.diagnostics, *coarse.diagnostics, *fine.diagnostics, *paint.diagnostics))))
