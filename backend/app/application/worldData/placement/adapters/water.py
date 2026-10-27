"""Declared water → common intents → resolved records, without a private resolve."""

from dataclasses import replace
from itertools import groupby

from app.application.jsonValidation.resolve import (
    ResolveContext, log_issues, reject_unresolved, report_issues, resolve_model,
)
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.placement.adapters.coastlineShape import coastline_cells
from app.application.worldData.placement.adapters.lakeShape import lake_cells, lake_level
from app.application.worldData.placement.adapters.waterShape import shape_cells
from app.application.worldData.placement.adapters.waterTypes import (
    PreparedWaterEntry, WaterGeometryError, WaterPlacementContext, WaterPlacementPreparation,
    WaterPreparationCode, WaterPreparationFailure,
)
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
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
                      anchors=dict(context.anchors), location_subtypes=dict(context.location_subtypes),
                      auto_specificity=dict(context.auto_specificity),
                      dependencies=dict(context.dependencies), permitted_overlaps=dict(context.permitted_overlaps),
                      separations=dict(context.separations))
    errors = []
    if any(not uid or uid != uid.strip() for uid in (context.world_uid, context.snapshot_uid)):
        errors.append(_context_issue(context, ctx,
                             "nonempty world/snapshot identities are required"))
    if type(context.snapshot_revision) is not bytes or len(context.snapshot_revision) != 32:
        errors.append(_context_issue(context, ctx, "snapshot revision must be a 32-byte output fingerprint"))
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


def _source_cells(source: DeclaredBasin | DeclaredCoastline | DeclaredLake,
                  hydrology: WorldHydrology, context: WaterPlacementContext,
                  ctx: ResolveContext, notices: list[FieldPathError],
                  ) -> tuple[frozenset, float] | WaterPreparationFailure:
    uid = source.location_uid
    try:
        if isinstance(source, DeclaredBasin):
            return shape_cells(source.footprint, uid, context)
        if isinstance(source, DeclaredCoastline):
            cells, capped = coastline_cells(source, context, hydrology.default_seas)
            # Area of this original fine-unit-square claim, before competition.
            if capped:
                notices.append(_source_issue(context, ctx, uid, WaterPreparationCode.CAP_REACHED,
                                      "coastline expansion reached hard area/extent budget"))
        else:
            cells, degenerate = lake_cells(source, context)
            if degenerate:
                notices.append(_source_issue(context, ctx, uid, WaterPreparationCode.DEGENERATE_RING,
                                       "shoreline has no interior; lake footprint is the contour itself"))
        return cells, float(len(cells))
    except WaterGeometryError as error:
        return WaterPreparationFailure(
            uid, _source_issue(context, ctx, uid, WaterPreparationCode.GEOMETRY, str(error)))


def _source_kind(source: DeclaredBasin | DeclaredCoastline | DeclaredLake) -> BasinKind:
    return source.kind if not isinstance(source, DeclaredLake) else BasinKind.LAKE


_PRIMARY_ORDER = (DeclaredBasin, DeclaredCoastline, DeclaredLake)


def _merged_issue(context: WaterPlacementContext, ctx: ResolveContext, uid: str,
                  members: list[tuple[str, int, DeclaredBasin | DeclaredCoastline | DeclaredLake]],
                  primary_index: int) -> FieldPathError:
    primary = members[primary_index][2]
    descriptor = ", ".join(f"{category}[{index}]" for category, index, _ in members)
    conflicts = [
        f"{category}[{index}] kind={_source_kind(source).value} liquid={source.liquid}"
        for position, (category, index, source) in enumerate(members)
        if position != primary_index
        and (_source_kind(source) != _source_kind(primary) or source.liquid != primary.liquid)
    ]
    reason = (f"duplicate declared water location_uid; merged {descriptor} into one source, "
              f"primary {members[primary_index][0]}[{members[primary_index][1]}]")
    if conflicts:
        reason += "; conflicts: " + "; ".join(conflicts)
    return _source_issue(context, ctx, uid, WaterPreparationCode.MERGED_SOURCES, reason)


def _build_entry(primary: DeclaredBasin | DeclaredCoastline | DeclaredLake,
                 cells: frozenset, area: float,
                 hydrology: WorldHydrology, context: WaterPlacementContext,
                 ctx: ResolveContext, notices: list[FieldPathError],
                 ) -> PreparedWaterEntry | WaterPreparationFailure:
    uid = primary.location_uid
    fact = None
    if isinstance(primary, DeclaredBasin):
        level = primary.z_water_level if primary.z_water_level is not None else hydrology.default_water_level
        floor = primary.floor_z
        kind, liquid = primary.kind, primary.liquid
    elif isinstance(primary, DeclaredCoastline):
        level = hydrology.default_water_level
        floor = level - hydrology.default_seas.basin_depth
        kind, liquid = primary.kind, primary.liquid
    else:
        kind, liquid = BasinKind.LAKE, primary.liquid
        level = lake_level(cells, context)
        floor = level - hydrology.default_lakes.basin_depth
    if floor < context.z_min or floor >= level:
        return WaterPreparationFailure(
            uid, _source_issue(context, ctx, uid, WaterPreparationCode.FLOOR,
                        "basin floor must satisfy world z_min <= floor_z < z_water_level"))
    if isinstance(primary, DeclaredCoastline):
        wet = any(context.surface_z[cell] < level for cell in cells)
        fact = CoastlinePlacementFact(snapshot_uid=context.snapshot_uid,
                                      water_presence=WaterPresence.PRESENT if wet else WaterPresence.ABSENT,
                                      reason="pre-carve footprint contains z < level" if wet
                                      else "no pre-carve footprint cell is below water level")
    subtype = context.location_subtypes.get(uid)
    if subtype is not None:
        try:
            declared = BasinKind(subtype.value)
        except ValueError:
            declared = None
        if declared is not None and declared != kind:
            notices.append(_source_issue(context, ctx, uid, WaterPreparationCode.KIND_MISMATCH,
                                   f"geographic subtype {subtype.value} differs from prepared kind "
                                   f"{kind.value}; prepared as {kind.value}"))
    intent = PlacementIntent(
        identity=PlacementIdentity(world_uid=context.world_uid, source_uid=uid, region_uid=uid),
        mode=PlacementMode.ABSOLUTE,
        shape=primary.footprint if isinstance(primary, DeclaredBasin) else None,
        placement_specificity=primary.placement_specificity if isinstance(primary, DeclaredBasin) else None,
        dependencies=context.dependencies.get(uid, ()),
        permitted_overlaps=context.permitted_overlaps.get(uid, ()),
        separations=context.separations.get(uid, ()),
    )
    candidate = PlacementCandidate(candidate_uid=uid, preference=0,
                                   footprint=PlacementFootprint(cells=cells, z_min=None, z_max=None))
    prepared = PreparedPlacement(intent=intent, original_area=area, candidates=(candidate,),
                                  auto_specificity=context.auto_specificity.get(uid), coastline=fact)
    return PreparedWaterEntry(primary, prepared, level, floor, kind, liquid)


def prepare_water_placements(hydrology: WorldHydrology, context: WaterPlacementContext, *,
                             ctx: ResolveContext) -> WaterPlacementPreparation:
    """Caller combines .objects with every ready domain before invoking P2."""
    hydrology = resolve_model(WorldHydrology, hydrology.model_dump(warnings=False), ctx=ctx)
    context = _validate_context(context, hydrology, ctx)
    entries, failures, notices = [], [], []
    tagged = sorted(
        [(category, index, source)
         for category, members in (("declared_basins", hydrology.declared_basins),
                                   ("declared_coastlines", hydrology.declared_coastlines),
                                   ("declared_lakes", hydrology.declared_lakes))
         for index, source in enumerate(members)],
        key=lambda item: item[2].location_uid)
    for uid, group in groupby(tagged, key=lambda item: item[2].location_uid):
        members = list(group)
        prepared_members = []
        for member in members:
            outcome = _source_cells(member[2], hydrology, context, ctx, notices)
            if isinstance(outcome, WaterPreparationFailure):
                failures.append(outcome)
            else:
                prepared_members.append((member, *outcome))
        if not prepared_members:
            continue
        if len(members) == 1:
            member, cells, area = prepared_members[0]
            primary = member[2]
        else:
            cells = frozenset().union(*(member_cells for _, member_cells, _ in prepared_members))
            area = float(len(cells))
            primary_position = min(
                range(len(prepared_members)),
                key=lambda position: (_PRIMARY_ORDER.index(type(prepared_members[position][0][2])),
                                      prepared_members[position][0][1]))
            primary = prepared_members[primary_position][0][2]
        outcome = _build_entry(primary, cells, area, hydrology, context, ctx, notices)
        if isinstance(outcome, WaterPreparationFailure):
            failures.append(outcome)
        else:
            if len(members) > 1:
                notices.append(_merged_issue(context, ctx, uid, members,
                                             members.index(prepared_members[primary_position][0])))
            entries.append(outcome)
    facts = [failure.issue for failure in failures] + notices
    if ctx.validate_only or ctx.collect_only:
        report_issues(ctx, facts)
    else:
        log_issues(facts)
    return WaterPlacementPreparation(context.world_uid, context.snapshot_uid, context.snapshot_revision, tuple(entries),
                                      tuple(failures), tuple(notices))


def resolved_water_placements(preparation: WaterPlacementPreparation,
                              result: PlacementBatchResult) -> tuple[ResolvedWaterPlacement, ...]:
    """Project a shared result; caller retains its unresolved and preparation failures."""
    if (result.world_uid != preparation.world_uid or result.snapshot_uid != preparation.snapshot_uid
            or result.snapshot_revision != preparation.snapshot_revision):
        raise ValueError("water preparation and common result must refer to the same world/snapshot/revision")
    outcomes = {outcome.identity.region_uid: outcome for outcome in result.results}
    records = []
    for entry in preparation.entries:
        uid = entry.prepared.intent.identity.region_uid
        outcome = outcomes.get(uid)
        if outcome is None or outcome.prepared != entry.prepared:
            raise ValueError(f"common batch must contain the exact water preparation: {uid}")
        if isinstance(outcome, ResolvedPlacement):
            records.append(ResolvedWaterPlacement(placement=outcome, z_water_level=entry.z_water_level,
                                                  kind=entry.kind, liquid=entry.liquid))
    return tuple(records)
