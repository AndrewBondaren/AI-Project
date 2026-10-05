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
from app.dataModel.locations.settlement.enums.districtDensity import (
    DistrictDensity,
)
from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import (
    WorldSettlementSizeRegistry,
)
from app.dataModel.materials import CONSTRUCTION_MATERIAL_DEFAULTS
from app.dataModel.shared.ranges import EconomicTierRange

ECONOMIC_TIER = Cascade(
    # Canonical authored/stamp field on NamedLocation-derived sources.
    field="system_economic_tier",
    default=DefaultPolicy.REGISTRY_MEDIAN,
    axis=ScopeLevel,
    input_types=((ChannelKind.RANGE, EconomicTierRange),),
    materialize="economic_tier",
    default_registry="economic_tiers",
)

CITY_SIZE = Cascade(
    # Settlement rank lives only at the settlement scope — deeper
    # scopes inherit it (cascade-migration M7, tz_cascade §5).
    field="system_city_size",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
    levels=(ScopeLevel.SETTLEMENT,),
    # Canonical rank (dataModel policy, not world registry).
    default_value=WorldSettlementSizeRegistry.default_system_size(),
)

SETTLEMENT_DENSITY = Cascade(
    # District-first chain — the district template is the deepest
    # (top) node and beats the settlement value; deeper scopes
    # inherit (cascade-migration M8, tz_cascade §5).
    field="settlement_density",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
    levels=(ScopeLevel.SETTLEMENT, ScopeLevel.DISTRICT),
    default_value=DistrictDensity.default(),
)

WALL_MATERIAL = Cascade(
    # NL `parent_wall_material` chain — the same field is the channel
    # node at every scope; a deeper authored NL overrides a shallower
    # one, ordering is by scope level (cascade-migration M9).
    field="parent_wall_material",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
    default_value=CONSTRUCTION_MATERIAL_DEFAULTS.wall,
)

FLOOR_MATERIAL = Cascade(
    # Same NL chain for `parent_floor_material` (M9).
    field="parent_floor_material",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
    default_value=CONSTRUCTION_MATERIAL_DEFAULTS.floor,
)

DOMINANT_MATERIAL = Cascade(
    # Settlement-only authored chain (NL node beats the skeleton node);
    # deeper scopes inherit. First `Cascade.fold` consumer (M10): the
    # tier→material_registry pick sits between the authored chain and
    # the canonical default; layout-derived dominants stay outside the
    # chain — they are post-assemble statistics over generated cells,
    # applied by the assembler on top of the ctx value (tz_city §3.1).
    field="dominant_material",
    default=DefaultPolicy.CANONICAL_DEFAULT,
    axis=ScopeLevel,
    levels=(ScopeLevel.SETTLEMENT,),
    fold="dominant_material",
    default_value=CONSTRUCTION_MATERIAL_DEFAULTS.dominant,
)
