"""Sparse final height delivery relative to the frozen natural window."""
from bisect import bisect_left

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan, require_coordinate_map, fine_order
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class FineHeightDeltaJob:
    def compute(self, before: FineSurfaceWindow, water: FineSurfaceWindow, *,
                samples: tuple[tuple[FineXY, FineZ], ...], river: RiverReliefPlan,
                control: PlanBuildControl) -> tuple[tuple[FineXY, FineZ], ...]:
        """Inputs are admitted immutable data; exact dependency refs belong to publication."""
        control.raise_if_shutdown()
        if before.topology != water.topology or before.coverage != water.coverage:
            raise ValueError("height delta requires the same frozen observation domain")
        require_coordinate_map(samples, fine_order)
        if tuple(c for c, _ in samples) != tuple(c for c, _ in river.fine_surface_z):
            raise ValueError("river relief must preserve exactly the retained H samples")
        beds = {cell for bed in river.fine_beds for cell, _ in bed.bed_z}
        for bed in river.fine_beds:
            for cell, z in bed.bed_z:
                control.raise_if_shutdown()
                i = bisect_left(river.fine_surface_z, (cell[1], cell[0]), key=lambda row: (row[0][1], row[0][0]))
                if i == len(river.fine_surface_z) or river.fine_surface_z[i] != (cell, z):
                    raise ValueError("actual bed must match the final river sample")
        for (cell, z), (_, final) in zip(samples, river.fine_surface_z, strict=True):
            control.raise_if_shutdown()
            i = bisect_left(water.surface_z, (cell[1], cell[0]), key=lambda row: (row[0][1], row[0][0]))
            if i == len(water.surface_z) or water.surface_z[i] != (cell, z):
                raise ValueError("H must match the canonical pre-river fine observation")
            if cell not in beds and final != z:
                raise ValueError("river relief changed a sample outside actual beds")
        final_rows = river.fine_surface_z
        result = []
        h = 0
        for old, current in zip(before.surface_z, water.surface_z, strict=True):
            control.raise_if_shutdown()
            cell, z = current
            if old[0] != cell:
                raise PlanBuildFailure((FieldPathError(("height_delta",), "frozen height observations must match"),))
            if h < len(final_rows) and final_rows[h][0] == cell:
                result.append(final_rows[h])
                h += 1
            elif old[1] != z:
                result.append(current)
        control.raise_if_shutdown()
        return tuple(result)
