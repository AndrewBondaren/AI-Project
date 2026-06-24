from app.db.models.namedLocation import NamedLocation


class TierResolver:
    """
    Resolves effective economic tier by cascading from most specific to most general.

    Order: room_tier → building → district → city → None

    Thread-safe: stateless, no shared mutable state.
    """

    @staticmethod
    def resolve(
        city:       NamedLocation | None = None,
        district:   NamedLocation | None = None,
        building:   NamedLocation | None = None,
        room_tier:  str | None = None,
    ) -> str | None:
        return (
            room_tier
            or (building  and building.system_economic_tier)
            or (district  and district.system_economic_tier)
            or (city      and city.system_economic_tier)
        )
