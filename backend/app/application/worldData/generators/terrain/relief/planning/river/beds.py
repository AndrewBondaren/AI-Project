"""Shared river-bed execution; preserves the historical pre-bed snapshot semantics."""
from collections.abc import Callable
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedZ import river_bed_spec, apply_river_bed_z
from app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedSpec import RiverBedSpec
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.relief.planning.reliefPlan import RiverBedRecord
from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def river_beds[S](routes: tuple[RiverRoute[S], ...], base: tuple[tuple[S, FineZ], ...], *,
                   topology: WorldTopology, world_uid: str, z_min: int,
                   depths: dict[HydrologyConnectionType, int], to_xy: Callable[[S], Coord],
                   from_xy: Callable[[Coord], S], control: PlanBuildControl,
                   ) -> tuple[tuple[tuple[S, FineZ], ...], tuple[RiverBedRecord[S], ...]]:
    bounds = topology.bounds
    surface = {to_xy(cell): int(z) for cell, z in base}
    snapshot = SurfaceHeightmap(world_uid=world_uid,
        bbox=GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max), surface_z=surface)
    specs: list[RiverBedSpec] = []
    cells_by_river: dict[str, set[Coord]] = {}
    for route in routes:
        control.raise_if_shutdown()
        receiver = to_xy(route.receiver_cell)
        targets: set[Coord] = set()
        for segment in route.segments:
            path = [to_xy(cell) for cell in segment.path]
            if any(cell not in surface or topology.canonicalize(*cell) != cell for cell in path):
                raise PlanBuildFailure((FieldPathError((SurfacePlanSlot.HYDROLOGY_ROUTES.value, route.river_uid),
                    "river path/receiver requires canonical pre-river heights"),))
            prepared = RiverSegment(polyline_cells=path, connection_type=segment.connection_type.value,
                edge_uid=segment.edge_uid, location_uid=segment.location_uid, declared=segment.declared)
            spec = river_bed_spec(snapshot, prepared, depth_step=depths[segment.connection_type],
                z_min=z_min, occupied={}, receiver_cell=receiver)
            specs.append(spec)
            targets.update(cell for cell, _ in spec.bed_z)
        if not targets:
            raise PlanBuildFailure((FieldPathError((SurfacePlanSlot.HYDROLOGY_ROUTES.value, route.river_uid),
                "accepted river requires nonempty land-bed cells"),))
        cells_by_river[route.river_uid] = targets
    # A tributary's receiver may be part of its parent river's bed. That parent
    # writes it; the tributary's own spec still excludes its terminal receiver.
    apply_river_bed_z(snapshot, specs)
    return (tuple((cell, FineZ(surface[to_xy(cell)])) for cell, _ in base),
        tuple(RiverBedRecord[S](river_uid=route.river_uid, bed_z=tuple(
            (from_xy(cell), FineZ(surface[cell])) for cell in sorted(cells_by_river[route.river_uid], key=lambda cell: (cell[1], cell[0]))))
            for route in routes))

