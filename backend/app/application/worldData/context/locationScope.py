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

from app.application.worldData.context.cascadeLink import Link
from app.application.worldData.context.contextResolver import extend
from app.application.worldData.generators.assemblers.citySkeleton import (
    settlement_skeleton_pojo,
)
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.namedLocation import BundleNamedLocation
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
