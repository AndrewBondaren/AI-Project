"""Build consistent final hydrology facts from accepted routes and actual beds."""

from app.application.worldData.generators.hydrology.planning.assembly.final.riverFacts import river_roles, require_receivers
from app.application.worldData.generators.hydrology.planning.assembly.final.nativeFacts import NativeFinalFactsJob
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, HydrologyRoutesPlan, RiverRoute
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverBedRecord, RiverReliefPlan
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


from app.application.worldData.generators.hydrology.planning.assembly.final.publication import NativeFinalPublicationJob
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput


def _failure(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("hydrology", "facts"), message),))


class HydrologyFactsAssembler:
    def publish_fine(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                     relief_inputs: RiverReliefInput, specs: tuple[BasinSpec, ...],
                     before: PlanEnvelope[FineSurfaceWindow], expected_before: PlanRef,
                     water: PlanEnvelope[FineWaterResult], expected_water: PlanRef,
                     routes: PlanEnvelope[GeoHydrologyRoutesPlan], expected_routes: PlanRef,
                     river: PlanEnvelope[RiverReliefPlan], expected_river: PlanRef,
                     control: PlanBuildControl) -> PlanEnvelope[GeoHydrologyPlan]:
        return NativeFinalPublicationJob().publish(world_uid=world_uid, inputs=inputs,
            relief_inputs=relief_inputs, specs=specs, before=before, expected_before=expected_before,
            water=water, expected_water=expected_water, routes=routes, expected_routes=expected_routes,
            river=river, expected_river=expected_river, control=control)

    def assemble_fine(self, *, inputs: GeoHydrologyPlanInput, before: FineSurfaceWindow,
                      water: FineWaterResult, routes: GeoHydrologyRoutesPlan, river: RiverReliefPlan,
                      control: PlanBuildControl) -> PlanBuildResult[GeoHydrologyPlan]:
        return NativeFinalFactsJob().assemble(inputs=inputs, before=before, water=water,
            routes=routes, river=river, control=control)

    def _require_coverage(self, inputs: HydrologyFinalInput, relief: ReliefPlan,
                          routes: HydrologyRoutesPlan, river: RiverReliefPlan) -> None:
        bounds = inputs.topology.bounds
        if (len(river.surface_z) != bounds.width * bounds.height or any(
                inputs.topology.canonicalize(cell.gx, cell.gy) != (cell.gx, cell.gy)
                for cell, _ in river.surface_z)):
            raise _failure("hydrology requires complete canonical pre-river relief")
        if ({cell for cell, _ in river.surface_z} != {cell for cell, _ in relief.surface_z}
                or {cell for cell, _ in river.fine_surface_z}
                != {cell for cell, _ in routes.fine_base_surface_z}):
            raise _failure("final river surface must preserve complete coarse and sampled fine coverage")

    def assemble(self, *, inputs: HydrologyFinalInput, relief: ReliefPlan,
                 routes: HydrologyRoutesPlan, river: RiverReliefPlan,
                 control: PlanBuildControl) -> PlanBuildResult[HydrologyPlan]:
        control.raise_if_shutdown()
        self._require_coverage(inputs, relief, routes, river)
        base = routes
        coarse: dict[Coord, MapCellHydrology] = {(cell.gx, cell.gy): value for cell, value in base.coarse_open_water}
        coarse.update(river_roles(base.coarse_routes, river.coarse_beds, river.surface_z,
                                      lambda cell: (cell.gx, cell.gy), control))
        fine = river_roles(base.fine_routes, river.fine_beds, river.fine_surface_z,
                                 lambda cell: cell, control)
        require_receivers(base.coarse_routes, coarse, lambda cell: (cell.gx, cell.gy))
        fine_top = fine_topology(inputs.topology, inputs.grid.fine_span)
        if any(fine_top.canonicalize(*cell) != cell for cell, _ in river.fine_surface_z):
            raise _failure("fine river samples outside final topology")
        span = inputs.grid.fine_span
        receivers = {route.receiver_cell: coarse[(route.receiver_cell[0] // span, route.receiver_cell[1] // span)]
            for route in base.fine_routes
            if (route.receiver_cell[0] // span, route.receiver_cell[1] // span) in coarse}
        require_receivers(base.fine_routes, receivers | fine, lambda cell: cell)
        if not inputs.enabled and (coarse or fine or base.water_bodies or base.physical_unions):
            raise _failure("disabled hydrology cannot consume active water facts")
        control.raise_if_shutdown()
        return PlanBuildResult[HydrologyPlan](payload=HydrologyPlan(
            coarse_surface_z=river.surface_z, fine_z_overrides=river.fine_surface_z,
            coarse_hydro=tuple((SurfaceGridCoord(GridX(cell[0]), GridY(cell[1])), coarse[cell]) for cell in sorted(coarse, key=lambda c: (c[1], c[0]))),
            sparse_fine_hydro=tuple(((FineX(cell[0]), FineY(cell[1])), fine[cell]) for cell in sorted(fine, key=lambda c: (c[1], c[0]))),
            water_bodies=base.water_bodies, physical_unions=base.physical_unions, declared_paint=base.declared_paint), diagnostics=())
