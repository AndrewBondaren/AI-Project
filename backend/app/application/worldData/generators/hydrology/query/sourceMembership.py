"""Encode physical open-water membership from admitted fine planning facts."""

from bisect import bisect_left
from collections.abc import Iterable, Iterator
from itertools import zip_longest

from app.application.planning.service.planningService import PlanBuildControl
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.hydrology.query.source import WaterMembershipRun
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.worldTopology import Coord


def _wet_facts(rows: Iterable[tuple[Coord, MapCellHydrology]],
               control: PlanBuildControl) -> Iterator[tuple[Coord, HydrologyCellRole, str | None, int | None]]:
    for cell, fact in rows:
        control.raise_if_shutdown()
        if fact.role is not None and fact.role.is_open_water_role():
            yield cell, fact.role, fact.water_body_uid, fact.z_water_level


def _levels(bodies: tuple[WaterBody, ...], control: PlanBuildControl) -> dict[str, int]:
    levels = {}
    for body in bodies:
        control.raise_if_shutdown()
        levels[body.water_body_uid] = body.z_water_level
    return levels


def build_wet_runs(*, water: FineWaterResult, final: GeoHydrologyPlan, bed: FineSurfaceWindow,
                   control: PlanBuildControl) -> tuple[WaterMembershipRun, ...]:
    control.raise_if_shutdown()
    post, assembled = water
    if (bed.topology != post.topology or bed.coverage != post.coverage
            or bed.protected_cells != post.protected_cells):
        raise ValueError("final bed must preserve the fine water frame, coverage and protection")

    materialized = assembled.materialized
    water_levels = _levels(materialized.bodies, control)
    final_levels = _levels(final.water_bodies, control)
    runs = []
    run_uid = None
    run_y = x0 = x1 = 0
    for source, native in zip_longest(_wet_facts(materialized.cells, control),
                                      _wet_facts(final.sparse_fine_hydro, control)):
        if source is None or source != native:
            raise ValueError("fine water and native final open-water facts disagree")
        (x, y), _, uid, level = source
        if uid is None or level is None or water_levels.get(uid) != level or final_levels.get(uid) != level:
            raise ValueError("wet fact requires the effective level of its body in both inputs")
        index = bisect_left(bed.surface_z, (y, x), key=lambda row: (row[0][1], row[0][0]))
        if index == len(bed.surface_z) or bed.surface_z[index][0] != (x, y):
            raise ValueError("wet cell lies outside observed bed coverage")
        if bed.surface_z[index][1] >= level:
            raise ValueError("wet cell requires final bed below effective level")

        if (y, x, uid) != (run_y, x1, run_uid):
            if run_uid is not None:
                runs.append(WaterMembershipRun(y=FineY(run_y), x0=FineX(x0), x1=FineX(x1), body_uid=run_uid))
            run_y, x0, run_uid = y, x, uid
        x1 = x + 1
    if run_uid is not None:
        runs.append(WaterMembershipRun(y=FineY(run_y), x0=FineX(x0), x1=FineX(x1), body_uid=run_uid))
    control.raise_if_shutdown()
    return tuple(runs)
