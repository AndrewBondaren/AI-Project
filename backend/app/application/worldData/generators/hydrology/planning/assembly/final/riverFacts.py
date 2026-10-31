"""Shared actual-bed roles and receiver validation for legacy and native final facts."""
from collections.abc import Callable, Mapping
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_roles
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.relief.planning.reliefPlan import RiverBedRecord
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _failure(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("hydrology", "facts"), message),))


def river_roles[S]( routes: tuple[RiverRoute[S], ...], beds: tuple[RiverBedRecord[S], ...],
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

def require_receivers[S]( routes: tuple[RiverRoute[S], ...], occupied: Mapping[Coord, MapCellHydrology],
                          to_xy: Callable[[S], Coord]) -> None:
    for route in routes:
        receiver = occupied.get(to_xy(route.receiver_cell))
        if receiver is None or receiver.water_body_uid != route.drainage.receiver_uid:
            raise _failure("accepted receiver must retain its actual receiving-water identity")

