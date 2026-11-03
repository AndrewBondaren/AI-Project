"""Assemble canonical open-water facts from revision-admitted planning payloads."""

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.query.sourceBed import build_source_bed
from app.application.worldData.generators.hydrology.query.sourceMembership import build_wet_runs
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.fineTopology import fine_topology


def build_source_payload(*, before: FineSurfaceWindow, water: FineWaterResult,
                         routes: GeoHydrologyRoutesPlan, river: RiverReliefPlan,
                         final: GeoHydrologyPlan, inputs: GeoHydrologyPlanInput,
                         control: PlanBuildControl) -> CanonicalOpenWaterSource:
    control.raise_if_shutdown()
    if before.topology != fine_topology(inputs.topology, inputs.grid.fine_span):
        raise ValueError("pre-water window must match the captured fine frame")

    post, assembled = water
    source = assembled.materialized
    if not source.bodies == routes.base.water_bodies == final.water_bodies:
        raise ValueError("physical body tables disagree across water, routes and final")
    if not assembled.physical_unions == routes.base.physical_unions == final.physical_unions:
        raise ValueError("physical union tables disagree across water, routes and final")
    if not source.source_mapping == routes.source_mapping == final.source_mapping:
        raise ValueError("source mappings disagree across water, routes and final")
    for body in source.bodies:
        control.raise_if_shutdown()
        if body.liquid not in inputs.liquid_keys:
            raise ValueError("body liquid is absent from captured material membership")

    bed = build_source_bed(before=before, post=post, routes=routes, river=river, final=final,
                           z_min=inputs.z_min, z_max=inputs.z_max, control=control)
    runs = build_wet_runs(water=water, final=final, bed=bed, control=control)
    shores = []
    for row in final.sparse_fine_hydro:
        control.raise_if_shutdown()
        if row[1].role is HydrologyCellRole.SHORE:
            shores.append(row)

    payload = CanonicalOpenWaterSource(space=CoordinateSpace.WORLD_FINE_GRID, bed=bed,
        z_min=inputs.z_min, z_max=inputs.z_max, wet_runs=runs,
        bodies=tuple(sorted(source.bodies, key=lambda b: b.water_body_uid)),
        unions=tuple(sorted(assembled.physical_unions, key=lambda u: u.water_system_uid)),
        source_mapping=source.source_mapping, shore_rows=tuple(shores))
    control.raise_if_shutdown()
    return payload
