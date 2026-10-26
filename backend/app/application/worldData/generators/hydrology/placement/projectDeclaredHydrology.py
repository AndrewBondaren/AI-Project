"""Declared hydrology in world fine units → the coarse working grid of the pre-1.4 pass."""

from pydantic import ValidationError

from app.application.jsonValidation.resolve import ResolveContext, log_issues, report_issues
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.generators.coordinates.convert import fine_to_grid_xy
from app.application.worldData.placement.adapters.waterTypes import WaterPreparationCode
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.worldHydrology import WorldHydrology


def _project_waypoints(waypoints: tuple[HydrologyWaypoint, ...], map_cell: int) -> list[HydrologyWaypoint]:
    return [
        waypoint.model_copy(update=dict(zip(("x", "y"), fine_to_grid_xy(waypoint.x, waypoint.y, map_cell))))
        for waypoint in waypoints
    ]


def _collapse_issue(ctx: ResolveContext, world_uid: str, collection: str, index: int,
                    source_uid: str, error: Exception) -> FieldPathError:
    return FieldPathError(
        path=ctx.path_prefix + ("hydrology", collection, index),
        code=WaterPreparationCode.GEOMETRY.value,
        schema_id=WorldHydrology.SCHEMA_ID,
        message=(f"world_uid={world_uid} source_uid={source_uid}; "
                 f"declared geometry collapses on the coarse working grid: {error}"),
    )


def project_declared_hydrology(hydrology: WorldHydrology, map_cell: int, *, ctx: ResolveContext,
                               world_uid: str) -> WorldHydrology:
    issues: list[FieldPathError] = []
    basins = []
    for index, basin in enumerate(hydrology.declared_basins):
        try:
            footprint = basin.footprint.projected(map_cell)
            basin = type(basin).model_validate(
                basin.model_dump() | {"footprint": footprint.model_dump()})
        except (ValidationError, ValueError) as error:
            issues.append(_collapse_issue(ctx, world_uid, "declared_basins", index,
                                          basin.location_uid, error))
            continue
        basins.append(basin)
    update: dict = {"declared_basins": basins}

    for collection, field in (("declared_coastlines", "path"), ("declared_lakes", "shoreline")):
        projected = []
        for index, entry in enumerate(getattr(hydrology, collection)):
            try:
                dump = entry.model_dump()
                dump[field] = [waypoint.model_dump()
                               for waypoint in _project_waypoints(getattr(entry, field), map_cell)]
                entry = type(entry).model_validate(dump)
            except (ValidationError, ValueError) as error:
                issues.append(_collapse_issue(ctx, world_uid, collection, index,
                                              entry.location_uid, error))
                continue
            projected.append(entry)
        update[collection] = projected
    if issues:
        facts = issues
        if ctx.validate_only or ctx.collect_only:
            report_issues(ctx, facts)
        else:
            log_issues(facts)
    return WorldHydrology.model_validate(
        hydrology.model_copy(update=update).model_dump(warnings=False))
