"""Declared water → common intents → resolved records, without a private resolve."""

from dataclasses import replace

from app.application.jsonValidation.resolve import (
    ResolveContext, log_issues, reject_unresolved, report_issues, resolve_model,
)
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.placement.adapters.coastlineShape import coastline_cells
from app.application.worldData.placement.adapters.waterShape import shape_cells
from app.application.worldData.placement.adapters.waterTypes import (
    PreparedWaterEntry, WaterGeometryError, WaterPlacementContext, WaterPlacementPreparation,
    WaterPreparationCode, WaterPreparationFailure,
)
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.placement import (
    CoastlinePlacementFact, PlacementBatchResult, PlacementCandidate, PlacementFootprint,
    PlacementIdentity, PlacementIntent, PlacementMode, PreparedPlacement, ResolvedPlacement,
    ResolvedWaterPlacement, WaterPresence,
)
from app.dataModel.topology.worldTopology import WorldTopology


def _context_issue(context: WaterPlacementContext, ctx: ResolveContext, reason: str) -> FieldPathError:
    return FieldPathError(path=ctx.path_prefix + ("water_placement",),
                          code=WaterPreparationCode.SNAPSHOT.value, schema_id=ctx.schema_id,
                          message=f"world_uid={context.world_uid} snapshot_uid={context.snapshot_uid}; {reason}")


def _source_issue(context: WaterPlacementContext, ctx: ResolveContext, source_uid: str,
                  code: WaterPreparationCode, reason: str) -> FieldPathError:
    return FieldPathError(path=ctx.path_prefix + ("water_placement", source_uid), code=code.value,
                          schema_id=ctx.schema_id,
                          message=f"world_uid={context.world_uid} snapshot_uid={context.snapshot_uid} "
                                  f"source_uid={source_uid}; {reason}")


def _validate_context(context: WaterPlacementContext, hydrology: WorldHydrology,
                      ctx: ResolveContext) -> WaterPlacementContext:
    topology = resolve_model(WorldTopology, context.topology.model_dump(), ctx=ctx.child("topology"))
    context = replace(context, topology=topology, surface_z=dict(context.surface_z),
                      anchors=dict(context.anchors), auto_specificity=dict(context.auto_specificity),
                      dependencies=dict(context.dependencies), permitted_overlaps=dict(context.permitted_overlaps),
                      separations=dict(context.separations))
    sources = [*hydrology.declared_basins, *hydrology.declared_coastlines]
    uids = [source.location_uid for source in sources]
    errors = []
    if any(not uid or uid != uid.strip() for uid in (context.world_uid, context.snapshot_uid)):
        errors.append(_context_issue(context, ctx,
                             "nonempty world/snapshot identities are required"))
    if len(uids) != len(set(uids)):
        errors.append(_context_issue(context, ctx,
                             "duplicate basin/coastline source UID"))
    bounds = topology.bounds
    if (len(context.surface_z) != bounds.width * bounds.height
            or any(len(cell) != 2 or any(type(value) is not int for value in cell)
                   or topology.canonicalize(*cell) != cell or type(z) is not int
                   for cell, z in context.surface_z.items())):
        errors.append(_context_issue(context, ctx,
                             "complete canonical world-fine pre-carve heightmap is required"))
    if (type(context.z_min) is not int
            or any(type(z) is int and z < context.z_min for z in context.surface_z.values())):
        errors.append(_context_issue(context, ctx,
                             "pre-carve elevation must respect integer world z_min"))
    for uid, point in context.anchors.items():
        if (len(point) != 2 or any(type(value) is not int for value in point)
                or topology.canonicalize(*point) is None):
            errors.append(_source_issue(context, ctx, uid, WaterPreparationCode.SNAPSHOT,
                                 "anchor must be a ready world-fine coordinate"))
    if errors:
        reject_unresolved(ctx, errors)
    return context


def prepare_water_placements(hydrology: WorldHydrology, context: WaterPlacementContext, *,
                             ctx: ResolveContext) -> WaterPlacementPreparation:
    """Caller combines .objects with every ready domain before invoking P2."""
    hydrology = resolve_model(WorldHydrology, hydrology.model_dump(warnings=False), ctx=ctx)
    context = _validate_context(context, hydrology, ctx)
    entries, failures, notices = [], [], []
    sources = sorted([*hydrology.declared_basins, *hydrology.declared_coastlines],
                     key=lambda source: source.location_uid)
    for source in sources:
        uid = source.location_uid
        basin = isinstance(source, DeclaredBasin)
        level = (source.z_water_level if source.z_water_level is not None else hydrology.default_water_level
                 ) if basin else hydrology.default_water_level
        floor = source.floor_z if basin else level - hydrology.default_seas.basin_depth
        if floor < context.z_min or floor >= level:
            issue = _source_issue(context, ctx, uid, WaterPreparationCode.FLOOR,
                           "basin floor must satisfy world z_min <= floor_z < z_water_level")
            failures.append(WaterPreparationFailure(uid, issue))
            continue
        try:
            if basin:
                cells, area = shape_cells(source.footprint, uid, context)
                fact = None
            else:
                cells, capped = coastline_cells(source, context, hydrology.default_seas)
                area = float(len(cells))  # Area of this original fine-unit-square claim, before competition.
                wet = any(context.surface_z[cell] < level for cell in cells)
                fact = CoastlinePlacementFact(snapshot_uid=context.snapshot_uid,
                                              water_presence=WaterPresence.PRESENT if wet else WaterPresence.ABSENT,
                                              reason="pre-carve footprint contains z < level" if wet
                                              else "no pre-carve footprint cell is below water level")
                if capped:
                    notices.append(_source_issue(context, ctx, uid, WaterPreparationCode.CAP_REACHED,
                                          "coastline expansion reached hard area/extent budget"))
        except WaterGeometryError as error:
            failures.append(WaterPreparationFailure(
                uid, _source_issue(context, ctx, uid, WaterPreparationCode.GEOMETRY, str(error))))
            continue
        intent = PlacementIntent(
            identity=PlacementIdentity(world_uid=context.world_uid, source_uid=uid, region_uid=uid),
            mode=PlacementMode.ABSOLUTE, shape=source.footprint if basin else None,
            placement_specificity=source.placement_specificity if basin else None,
            dependencies=context.dependencies.get(uid, ()),
            permitted_overlaps=context.permitted_overlaps.get(uid, ()),
            separations=context.separations.get(uid, ()),
        )
        candidate = PlacementCandidate(candidate_uid=uid, preference=0,
                                       footprint=PlacementFootprint(cells=cells, z_min=None, z_max=None))
        prepared = PreparedPlacement(intent=intent, original_area=area, candidates=(candidate,),
                                      auto_specificity=context.auto_specificity.get(uid), coastline=fact)
        entries.append(PreparedWaterEntry(source, prepared, level))
    facts = [failure.issue for failure in failures] + notices
    if ctx.validate_only:
        report_issues(ctx, facts)
    else:
        log_issues(facts)
    return WaterPlacementPreparation(context.world_uid, context.snapshot_uid, tuple(entries),
                                      tuple(failures), tuple(notices))


def resolved_water_placements(preparation: WaterPlacementPreparation,
                              result: PlacementBatchResult) -> tuple[ResolvedWaterPlacement, ...]:
    """Project a shared result; caller retains its unresolved and preparation failures."""
    if result.world_uid != preparation.world_uid or result.snapshot_uid != preparation.snapshot_uid:
        raise ValueError("water preparation and common result must refer to the same world/snapshot")
    outcomes = {outcome.prepared.intent.identity.region_uid: outcome for outcome in result.results}
    records = []
    for entry in preparation.entries:
        uid = entry.prepared.intent.identity.region_uid
        outcome = outcomes.get(uid)
        if outcome is None or outcome.prepared != entry.prepared:
            raise ValueError(f"common batch must contain the exact water preparation: {uid}")
        if isinstance(outcome, ResolvedPlacement):
            records.append(ResolvedWaterPlacement(placement=outcome, z_water_level=entry.z_water_level,
                                                  kind=entry.source.kind, liquid=entry.source.liquid))
    return tuple(records)
