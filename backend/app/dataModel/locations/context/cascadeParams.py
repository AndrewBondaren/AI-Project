"""Cascade parameter objects — each declared once, referenced by
identity from the ``LocationContext`` field and every source channel
(``CascadeChannel.param is ECONOMIC_TIER``). Renaming a constant breaks
the import instead of silently degrading to inherit/default
(tz_cascade_context §3).
"""

from app.dataModel.cascade.cascadeSpec import (
    Cascade,
    ChannelKind,
    DefaultPolicy,
)
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.shared.ranges import EconomicTierRange

ECONOMIC_TIER = Cascade(
    # Canonical authored/stamp field on NamedLocation-derived sources.
    field="system_economic_tier",
    default=DefaultPolicy.REGISTRY_MEDIAN,
    axis=ScopeLevel,
    input_types=((ChannelKind.RANGE, EconomicTierRange),),
)

CITY_SIZE = Cascade(
    # Settlement rank lives only at the settlement scope — deeper
    # scopes inherit it (cascade-migration M7, tz_cascade §5).
    field="system_city_size",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
    levels=(ScopeLevel.SETTLEMENT,),
)

SETTLEMENT_DENSITY = Cascade(
    # District-first chain — the district template is the deepest
    # (top) node and beats the settlement value; deeper scopes
    # inherit (cascade-migration M8, tz_cascade §5).
    field="settlement_density",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
    levels=(ScopeLevel.SETTLEMENT, ScopeLevel.DISTRICT),
)

WALL_MATERIAL = Cascade(
    # NL `parent_wall_material` chain — the same field is the channel
    # node at every scope; a deeper authored NL overrides a shallower
    # one, ordering is by scope level (cascade-migration M9).
    field="parent_wall_material",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
)

FLOOR_MATERIAL = Cascade(
    # Same NL chain for `parent_floor_material` (M9).
    field="parent_floor_material",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
)
