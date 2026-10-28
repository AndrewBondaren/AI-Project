"""Declared hydrology in world fine units → the coarse working grid of the pre-1.4 pass."""

from pydantic import ValidationError

from app.application.jsonValidation.resolve import ResolveContext, log_issues, report_issues
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.placement.adapters.waterTypes import WaterPreparationCode
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.worldHydrology import WorldHydrology


def _project_waypoints(waypoints: tuple[HydrologyWaypoint, ...], map_cell: int) -> tuple[HydrologyWaypoint, ...]:
    return tuple(HydrologyWaypoint(x=point.x // map_cell, y=point.y // map_cell, z=point.z) for point in waypoints)


def project_water_source[S: DeclaredBasin | DeclaredCoastline | DeclaredLake](source: S, map_cell: int) -> S:
    """Typed single-source projection shared by G5 and the existing caller.

    Only this serialization boundary rebuilds legacy POJOs. No temporary
    WorldHydrology is needed to project one captured authored source.
    """
    if not isinstance(source, (DeclaredBasin, DeclaredCoastline, DeclaredLake)):
        raise TypeError("source projection requires a typed authored water source")
    if isinstance(source, DeclaredCoastline) and not source.is_water_source:
        raise ValueError("body_boundary belongs to dependent preparation, not water source projection")
    if type(map_cell) is not int or map_cell <= 0:
        raise ValueError("source projection requires a positive integer fine span")
    if isinstance(source, DeclaredBasin):
        return type(source).model_validate(source.model_dump() | {"footprint": source.footprint.projected(map_cell)})
    if isinstance(source, DeclaredCoastline):
        return type(source).model_validate(source.model_dump() | {"path": _project_waypoints(source.path, map_cell)})
    return type(source).model_validate(source.model_dump() | {"shoreline": _project_waypoints(source.shoreline, map_cell)})


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
            basin = project_water_source(basin, map_cell)
        except (ValidationError, ValueError) as error:
            issues.append(_collapse_issue(ctx, world_uid, "declared_basins", index,
                                          basin.location_uid, error))
            continue
        basins.append(basin)
    update: dict = {"declared_basins": basins}

    for collection, members in (("declared_coastlines", hydrology.declared_coastlines), ("declared_lakes", hydrology.declared_lakes)):
        projected = []
        for index, entry in enumerate(members):
            if isinstance(entry, DeclaredCoastline) and not entry.is_water_source:
                # Boundary path stays authored for its dependent phase; this is
                # the body projection pass, not a boundary geometry producer.
                projected.append(entry)
                continue
            try:
                entry = project_water_source(entry, map_cell)
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
