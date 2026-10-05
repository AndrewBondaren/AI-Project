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

    @classmethod
    def containment_parents(cls) -> dict["ScopeLevel", frozenset["ScopeLevel"]]:
        """Legal direct containers per scope tag.

        Mirrors the `parent_types` registry shape (a building may hang
        under settlement/district — standalone or inside a generated
        plot area). New tags (GEOGRAPHIC, DUNGEON, LEVEL…) arrive with
        their payload types — nl-typed-host-payload plan.
        """
        return {
            cls.WORLD: frozenset(),
            cls.SETTLEMENT: frozenset({cls.WORLD}),
            cls.DISTRICT: frozenset({cls.SETTLEMENT}),
            cls.AREA: frozenset({cls.DISTRICT}),
            cls.BUILDING: frozenset(
                {cls.AREA, cls.DISTRICT, cls.SETTLEMENT}
            ),
            cls.ROOM: frozenset({cls.BUILDING}),
        }
