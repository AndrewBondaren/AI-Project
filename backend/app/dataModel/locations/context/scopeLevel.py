"""Location scope axis — tz_cascade_context §2.

The canonical location hierarchy: world → settlement → district → area
→ building → room. One axis among potentially many — other domains
(factions, magic) declare their own ``ScopeAxis`` enums; the cascade
mechanism is axis-agnostic and binds each parameter to its axis via
``Cascade.axis``.
"""

from app.dataModel.cascade.cascadeSpec import ScopeAxis


class ScopeLevel(ScopeAxis):
    WORLD = "world"
    SETTLEMENT = "settlement"
    DISTRICT = "district"
    AREA = "area"
    BUILDING = "building"
    ROOM = "room"
