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
