"""Location-axis scope-boundary helpers — tz_cascade_context §2, §4.

Caller-side glue of the cascade contract: runtime/persist objects
(``NamedLocation`` dataclass) are converted to their source POJO here,
and the per-scope materialize rng is seeded once per scope+param
(``Random(make_scope_seed(world_uid, scope_uid, param))``). The engine
stays generic (``contextResolver.extend``); these factories are the
location domain's boundary wiring — one per scope level.
"""

import hashlib
from dataclasses import asdict
from random import Random

from app.application.worldData.context.cascadeLink import EmptyLink, Link
from app.application.worldData.context.contextResolver import extend
from app.application.worldData.generators.assemblers.citySkeleton import (
    settlement_skeleton_pojo,
)
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.namedLocation import BundleNamedLocation
from app.dataModel.locations.settlement.district.districtTemplateEntry import (
    DistrictTemplateEntry,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def named_location_pojo(location: NamedLocation) -> BundleNamedLocation:
    """Persist/runtime ``NamedLocation`` → its source POJO (§2)."""
    return BundleNamedLocation.model_validate(asdict(location))


def make_scope_seed(world_uid: str, scope_uid: str, param: str) -> int:
    """Seed of the scope's materialize rng — one per scope+param (§4)."""
    raw = (world_uid + scope_uid + param).encode()
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


def settlement_context(
    world: World,
    settlement: NamedLocation,
) -> LocationContext:
    """World root + settlement links → resolved settlement-scope ctx."""
    return extend(
        LocationContext.root(world),
        Link(ScopeLevel.SETTLEMENT, named_location_pojo(settlement)),
        Link(ScopeLevel.SETTLEMENT, settlement_skeleton_pojo(settlement)),
        rng=Random(
            make_scope_seed(
                world.world_uid, settlement.location_uid, "tier",
            ),
        ),
    )


def district_context(
    world: World,
    ctx: LocationContext,
    template: DistrictTemplateEntry,
    *,
    district: NamedLocation | None = None,
    district_uid: str,
) -> LocationContext:
    """Settlement ctx + district links → district-scope ctx (§8.4).

    The persisted/authored district NL is the first link when known —
    its ``system_economic_tier`` beats the template range.
    """
    links = [Link(ScopeLevel.DISTRICT, template)]
    if district is not None:
        links.insert(
            0,
            Link(ScopeLevel.DISTRICT, named_location_pojo(district)),
        )
    return extend(
        ctx,
        *links,
        rng=Random(make_scope_seed(world.world_uid, district_uid, "tier")),
    )


def area_context(
    world: World,
    ctx: LocationContext,
    plot: PlotLayoutTemplate,
    *,
    area_uid: str,
) -> LocationContext:
    """District ctx + plot link → area-scope ctx."""
    return extend(
        ctx,
        Link(ScopeLevel.AREA, plot),
        rng=Random(make_scope_seed(world.world_uid, area_uid, "tier")),
    )


def building_context(
    world: World,
    ctx: LocationContext,
    building: NamedLocation,
) -> LocationContext:
    """Area ctx + building NL link → building-scope ctx."""
    return extend(
        ctx,
        Link(ScopeLevel.BUILDING, named_location_pojo(building)),
        rng=Random(
            make_scope_seed(world.world_uid, building.location_uid, "tier"),
        ),
    )


def empty_location_chain(world: World, up_to: ScopeLevel) -> LocationContext:
    """Root → declared-empty levels down to ``up_to`` (§4 EmptyLink).

    For callers that genuinely own no upper scopes (hand-built/debug
    inputs); each level is declared, never skipped silently.
    """
    ctx = LocationContext.root(world)
    for scope in ScopeLevel:
        if scope is ScopeLevel.WORLD:
            continue
        ctx = extend(ctx, EmptyLink(scope))
        if scope is up_to:
            break
    return ctx
