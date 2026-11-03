"""Build the complete final bed from admitted native planning payloads."""

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.planning.projection.heightDelta import FineHeightDeltaJob
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow


# GEO-LEGACY-71: Use native route samples and the independently published final delta.
def build_source_bed(*, before: FineSurfaceWindow, post: FineSurfaceWindow,
                     routes: GeoHydrologyRoutesPlan, river: RiverReliefPlan,
                     final: GeoHydrologyPlan, z_min: FineZ, z_max: FineZ,
                     control: PlanBuildControl) -> FineSurfaceWindow:
    control.raise_if_shutdown()
    if before.protected_cells != post.protected_cells:
        raise ValueError("post-water window must preserve pre-water protection")
    if z_min > z_max:
        raise ValueError("source bed requires ordered vertical bounds")

    delta = FineHeightDeltaJob().compute(before, post, samples=routes.base.fine_base_surface_z,
                                         river=river, control=control)
    if delta != final.fine_z_overrides:
        raise ValueError("native final height delta disagrees with water and river geometry")

    overlay = iter(river.fine_surface_z)
    sample = next(overlay, None)
    rows = []
    for cell, z in post.surface_z:
        control.raise_if_shutdown()
        if sample is not None and sample[0] == cell:
            z = sample[1]
            sample = next(overlay, None)
        if not z_min <= z <= z_max:
            raise ValueError("final bed elevation exceeds captured vertical bounds")
        rows.append((cell, z))

    bed = FineSurfaceWindow(coverage=before.coverage, topology=before.topology,
                            protected_cells=before.protected_cells, surface_z=tuple(rows))
    control.raise_if_shutdown()
    return bed
