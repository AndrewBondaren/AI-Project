"""Carve accepted native fine routes and project their actual post-bed geometry."""
from bisect import bisect_left

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.terrain.relief.planning.river.beds import river_beds
from app.application.worldData.generators.terrain.planning.projection.coarseSurface import CoarseSurfaceProjectionJob
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class NativeRiverReliefJob:
    def plan(self, inputs: RiverReliefInput, *, world_uid: EntityUid, water: FineWaterResult,
             routes: GeoHydrologyRoutesPlan, control: PlanBuildControl) -> RiverReliefPlan:
        """Envelope/source identity is admitted once by the publication boundary."""
        control.raise_if_shutdown()
        window = water[0]
        rows = window.surface_z
        base = routes.base
        for cell, z in base.fine_base_surface_z:
            control.raise_if_shutdown()
            i = bisect_left(rows, (cell[1], cell[0]), key=lambda row: (row[0][1], row[0][0]))
            if i == len(rows) or rows[i] != (cell, z):
                raise PlanBuildFailure((FieldPathError(("river_relief", *cell),
                    "retained pre-river height must match canonical fine water"),))
        fine_surface, beds = river_beds(base.fine_routes, base.fine_base_surface_z,
            topology=window.topology, world_uid=world_uid, z_min=inputs.z_min,
            depths=dict(inputs.channel_depths), to_xy=lambda cell: cell,
            from_xy=lambda cell: (FineX(cell[0]), FineY(cell[1])), control=control)
        coarse = CoarseSurfaceProjectionJob().project(window, topology=inputs.topology,
            grid=inputs.grid, control=control, overlay=fine_surface)
        control.raise_if_shutdown()
        return RiverReliefPlan(surface_z=coarse.surface_z, fine_surface_z=fine_surface,
                               coarse_beds=(), fine_beds=beds)
