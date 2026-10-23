"""Build consistent final hydrology facts from accepted routes and actual beds."""

from collections.abc import Callable, Mapping

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_roles
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, HydrologyRoutesPlan, RiverRoute
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverBedRecord, RiverReliefPlan
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _failure(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("hydrology", "facts"), message),))


class HydrologyFactsAssembler:
    def _river_roles[S](self, routes: tuple[RiverRoute[S], ...], beds: tuple[RiverBedRecord[S], ...],
                        surface: tuple[tuple[S, FineZ], ...], to_xy: Callable[[S], Coord],
                        control: PlanBuildControl) -> dict[Coord, MapCellHydrology]:
        records = {bed.river_uid: dict(bed.bed_z) for bed in beds}
        if set(records) != {route.river_uid for route in routes}:
            raise _failure("actual river beds must join accepted routes by UID in each space")
        heights = dict(surface)
        result = {}
        for route in routes:
            control.raise_if_shutdown()
            record = records[route.river_uid]
            expected = {cell for segment in route.segments for cell in segment.path if cell != route.receiver_cell}
            if (set(record) != expected or route.receiver_cell not in heights
                    or any(heights.get(cell) != z for cell, z in record.items())):
                raise _failure("incomplete or inconsistent actual bed/receiver mapping")
            for segment in route.segments:
                prepared = RiverSegment([to_xy(cell) for cell in segment.path], segment.connection_type.value,
                    edge_uid=segment.edge_uid, location_uid=segment.location_uid, declared=segment.declared)
                spec = RiverBedSpec(tuple((to_xy(cell), record[cell]) for cell in segment.path if cell in record))
                result.update(river_bed_roles(prepared, spec, drainage=route.drainage))
        return result

    def _require_receivers[S](self, routes: tuple[RiverRoute[S], ...], occupied: Mapping[Coord, MapCellHydrology],
                              to_xy: Callable[[S], Coord]) -> None:
        for route in routes:
            receiver = occupied.get(to_xy(route.receiver_cell))
            if receiver is None or receiver.water_body_uid != route.drainage.receiver_uid:
                raise _failure("accepted receiver must retain its actual receiving-water identity")

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
        coarse.update(self._river_roles(base.coarse_routes, river.coarse_beds, river.surface_z,
                                      lambda cell: (cell.gx, cell.gy), control))
        fine = self._river_roles(base.fine_routes, river.fine_beds, river.fine_surface_z,
                                 lambda cell: cell, control)
        self._require_receivers(base.coarse_routes, coarse, lambda cell: (cell.gx, cell.gy))
        fine_top = fine_topology(inputs.topology, inputs.grid.fine_span)
        if any(fine_top.canonicalize(*cell) != cell for cell, _ in river.fine_surface_z):
            raise _failure("fine river samples outside final topology")
        span = inputs.grid.fine_span
        receivers = {route.receiver_cell: coarse[(route.receiver_cell[0] // span, route.receiver_cell[1] // span)]
            for route in base.fine_routes
            if (route.receiver_cell[0] // span, route.receiver_cell[1] // span) in coarse}
        self._require_receivers(base.fine_routes, receivers | fine, lambda cell: cell)
        if not inputs.enabled and (coarse or fine or base.water_bodies or base.physical_unions):
            raise _failure("disabled hydrology cannot consume active water facts")
        control.raise_if_shutdown()
        return PlanBuildResult[HydrologyPlan](payload=HydrologyPlan(
            coarse_surface_z=river.surface_z, fine_z_overrides=river.fine_surface_z,
            coarse_hydro=tuple((SurfaceGridCoord(GridX(cell[0]), GridY(cell[1])), coarse[cell]) for cell in sorted(coarse, key=lambda c: (c[1], c[0]))),
            sparse_fine_hydro=tuple(((FineX(cell[0]), FineY(cell[1])), fine[cell]) for cell in sorted(fine, key=lambda c: (c[1], c[0]))),
            water_bodies=base.water_bodies, physical_unions=base.physical_unions, declared_paint=base.declared_paint), diagnostics=())
