"""Location-axis scope-boundary helpers — tz_cascade_context §2, §4.

Caller-side glue of the cascade contract: runtime/persist objects
(``NamedLocation`` dataclass) are converted to their source POJO here,
and the per-scope materialize rng is seeded once per scope+param
(``scope_rng(world_uid, scope_uid, param)``). The engine
stays generic (``contextResolver.extend``); these factories are the
location domain's boundary wiring — one per scope level.
"""

from dataclasses import asdict
from app.application.worldData.locationPayloadAccess import settlement_payload
from random import Random

from app.application.jsonValidation import economic_tiers, location_types
from app.application.jsonValidation.resolve import ResolveContext, resolve_model
from app.application.jsonValidation.sourceValidation import validate_source

from app.application.worldData.context.cascadeLink import EmptyLink, Link
from app.application.worldData.context.contextResolver import extend, scope_sequence
from app.ids import UidKind, entity_rng
from app.application.worldData.settlementSkeletonAccess import settlement_skeleton_pojo
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.context.locationCascadeDefaults import LocationCascadeDefaults
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.namedLocation import BundleNamedLocation
from app.dataModel.locations.settlement.district.districtTemplateEntry import (
    DistrictTemplateEntry,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
)
from app.dataModel.locations.structure.room.roomDef import RoomDef
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def named_location_pojo(location: NamedLocation, *, world: World | None = None, resolve_ctx: ResolveContext | None = None) -> BundleNamedLocation:
    """Persist/runtime ``NamedLocation`` → its source POJO (§2)."""
    return resolve_model(BundleNamedLocation, asdict(location),
        ctx=resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("locations", location.location_uid)),
        validation_context={"location_type_registry": location_types(world)} if world is not None else None)


def scope_rng(world_uid: str, scope_uid: str, param: str) -> Random:
    """Stream of the scope's materialize rng — one per scope+param (§4)."""
    return entity_rng(world_uid, UidKind.CASCADE, scope=scope_uid, param=param)


def root_context(world: World) -> LocationContext:
    """Caller boundary: world accessor → typed, lazily read default POJO."""
    return LocationContext.root(
        world,
        default_sources=(LocationCascadeDefaults(tier_registry=economic_tiers(world)),),
    )


def settlement_context(
    world: World,
    settlement: NamedLocation,
    *, resolve_ctx: ResolveContext | None = None,
) -> LocationContext:
    """World root + settlement links → resolved settlement-scope ctx."""
    sources = (named_location_pojo(settlement, world=world, resolve_ctx=resolve_ctx), settlement_payload(settlement, ctx=resolve_ctx),
               settlement_skeleton_pojo(settlement, ctx=resolve_ctx))
    for source in sources:
        validate_source(world, source, ctx=resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("locations", settlement.location_uid)))
    return extend(
        root_context(world),
        *(Link(ScopeLevel.SETTLEMENT, source) for source in sources),
        rng=scope_rng(world.world_uid, settlement.location_uid, "tier"),
    )


def district_context(
    world: World,
    ctx: LocationContext,
    template: DistrictTemplateEntry,
    *,
    district: NamedLocation | None = None,
    district_uid: str,
    resolve_ctx: ResolveContext | None = None,
) -> LocationContext:
    """Settlement ctx + district links → district-scope ctx (§8.4).

    The persisted/authored district NL is the first link when known —
    its ``system_economic_tier`` beats the template range.
    """
    links = [Link(ScopeLevel.DISTRICT, template)]
    if district is not None:
        links.insert(
            0,
            Link(ScopeLevel.DISTRICT, named_location_pojo(district, world=world, resolve_ctx=resolve_ctx)),
        )
    for link in links:
        validate_source(world, link.obj, ctx=resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("districts", district_uid)))
    return extend(
        ctx,
        *links,
        rng=scope_rng(world.world_uid, district_uid, "tier"),
    )


def area_context(
    world: World,
    ctx: LocationContext,
    plot: PlotLayoutTemplate,
    *,
    area_uid: str,
    resolve_ctx: ResolveContext | None = None,
) -> LocationContext:
    """District ctx + plot link → area-scope ctx."""
    validate_source(world, plot, ctx=resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("areas", area_uid)))
    return extend(
        ctx,
        Link(ScopeLevel.AREA, plot),
        rng=scope_rng(world.world_uid, area_uid, "tier"),
    )


def building_context(
    world: World,
    ctx: LocationContext,
    building: NamedLocation,
    *, resolve_ctx: ResolveContext | None = None,
) -> LocationContext:
    """Area ctx + building NL link → building-scope ctx."""
    source = named_location_pojo(building, world=world, resolve_ctx=resolve_ctx)
    validate_source(world, source, ctx=resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("locations", building.location_uid)))
    return extend(
        ctx,
        Link(ScopeLevel.BUILDING, source),
        rng=scope_rng(world.world_uid, building.location_uid, "tier"),
    )


def room_context(
    world: World,
    ctx: LocationContext,
    room_def: RoomDef,
    *,
    room_uid: str,
    resolve_ctx: ResolveContext | None = None,
) -> LocationContext:
    """Building ctx + room_def link → room-scope ctx."""
    active_ctx = resolve_ctx if resolve_ctx is not None else ResolveContext(path_prefix=("rooms", room_def.room_id))
    validate_source(world, room_def, ctx=active_ctx)
    return extend(
        ctx,
        Link(ScopeLevel.ROOM, room_def),
        rng=scope_rng(world.world_uid, room_uid, "tier"),
    )


def debug_building_context(
    world: World,
    building: NamedLocation,
    plot: PlotLayoutTemplate | None = None,
) -> LocationContext:
    """Ad-hoc building ctx for debug/test callers without a real chain.

    Empty scopes stand in for settlement/district; a probe plot — when
    given — materializes the area scope through the real cascade
    (§4 EmptyLink; cascade-migration M5 debug contract).
    """
    ctx = empty_location_chain(world, ScopeLevel.DISTRICT)
    ctx = (
        area_context(
            world, ctx, plot,
            area_uid=f"{building.location_uid}#area",
        )
        if plot is not None
        else extend(ctx, EmptyLink(ScopeLevel.AREA))
    )
    return building_context(world, ctx, building)


def empty_location_chain(world: World, up_to: ScopeLevel) -> LocationContext:
    """Root → declared-empty levels down to ``up_to`` (§4 EmptyLink).

    For callers that genuinely own no upper scopes (hand-built/debug
    inputs); each level is declared, never skipped silently.
    """
    ctx = root_context(world)
    path = scope_sequence(ctx)
    if up_to not in path:
        raise ValueError(f"no declared cascade boundary for {up_to.value}")
    if up_to is ctx.level:
        return ctx
    for scope in path[1:]:
        ctx = extend(ctx, EmptyLink(scope))
        if scope is up_to:
            break
    return ctx
