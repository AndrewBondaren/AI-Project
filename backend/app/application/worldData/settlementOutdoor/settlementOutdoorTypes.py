"""Location-type keys for outdoor extract — registry only, no string fallback."""

from __future__ import annotations

from app.dataModel.locations.locationType.locationTypeEntry import LocationTypeEntry
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)


class SettlementOutdoorTypeError(ValueError):
    """Engine location_type_registry missing a required type."""


def _engine() -> WorldLocationTypeRegistry:
    return WorldLocationTypeRegistry.canonical_engine()


def require_location_type(system_type: str) -> LocationTypeEntry:
    entry = _engine().entry_for(system_type)
    if entry is None:
        raise SettlementOutdoorTypeError(
            f"location_type_registry missing system_type={system_type!r}"
        )
    return entry


def district_type_entry() -> LocationTypeEntry:
    return require_location_type(WorldLocationTypeRegistry.SYSTEM_TYPE_DISTRICT)


def building_type_entry() -> LocationTypeEntry:
    return require_location_type(WorldLocationTypeRegistry.SYSTEM_TYPE_BUILDING)


def is_district_location(system_location_type: str | None) -> bool:
    if not system_location_type:
        return False
    return system_location_type == district_type_entry().system_type
