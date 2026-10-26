"""Order public hydrology operations and assemble their immutable results."""

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.application.worldData.generators.hydrology.load.paint.declaredWaterPaintProjector import DeclaredWaterPaintProjector
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan


class HydrologyRoutesAssembler:
    def __init__(self, water: WaterBodyPlanner, coarse: CoarseRiverPlanner,
                 fine: FineRiverPlanner, paint: DeclaredWaterPaintProjector) -> None:
        self._water, self._coarse, self._fine, self._paint = water, coarse, fine, paint

    def assemble(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput,
                 relief: ReliefPlan, placement: WaterPlacementPlan,
                 control: PlanBuildControl) -> PlanBuildResult[HydrologyRoutesPlan]:
        control.raise_if_shutdown()
        water = self._water.plan(world_uid=world_uid, inputs=inputs,
            surface_z=relief.surface_z, placement=placement, control=control)
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
