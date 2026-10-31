"""Point projection of an admitted fine surface; no natural recipe evaluation."""
from bisect import bisect_left

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.coordinates.light.grid import light_cell_center_fine
from app.dataModel.spatial.grid.coordinateTypes import FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class CoarseSurfaceProjectionJob:
    def project(self, surface: FineSurfaceWindow, *, topology: WorldTopology,
                grid: SurfaceGridSettings, control: PlanBuildControl) -> TerrainPlan:
        control.raise_if_shutdown()
        if surface.topology != fine_topology(topology, grid.fine_span):
            raise ValueError("coarse surface projection requires the matching fine topology")
        bounds, rows = topology.bounds, surface.surface_z
        scale = LightGridScale.from_tile(grid.fine_span, 1)
        projected = []
        for gy in range(bounds.y_min, bounds.y_max+1):
            control.raise_if_shutdown()
            for gx in range(bounds.x_min, bounds.x_max+1):
                x, y = light_cell_center_fine(gx, gy, 0, 0, scale)
                i = bisect_left(rows, (y, x), key=lambda row: (row[0][1], row[0][0]))
                if i == len(rows) or rows[i][0] != (x, y):
                    raise PlanBuildFailure((FieldPathError(("projection", gx, gy), "missing fine height observation"),))
                projected.append((SurfaceGridCoord(GridX(gx), GridY(gy)), FineZ(rows[i][1])))
        control.raise_if_shutdown()
        return TerrainPlan(bbox=GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max),
                           surface_z=tuple(projected))


class TerrainProjectionPlanner:
    def project_coarse(self, surface: FineSurfaceWindow, *, topology: WorldTopology,
                       grid: SurfaceGridSettings, control: PlanBuildControl) -> TerrainPlan:
        return CoarseSurfaceProjectionJob().project(surface, topology=topology, grid=grid, control=control)
