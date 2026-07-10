"""Settlement vs pin territory — derived from location/city-size registries (REVIEW-3)."""

from __future__ import annotations

from functools import lru_cache

from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry
from app.dataModel.settlement.settlement.worldCitySizeRegistry import WorldCitySizeRegistry

_LEGACY_FOOTPRINT_SYSTEM_TYPES = frozenset({"city"})
_LEGACY_SIZE_ALIASES = frozenset({"camp"})


@lru_cache(maxsize=1)
def _footprint_system_types() -> frozenset[str]:
    return frozenset({"settlement", "district"}) | _LEGACY_FOOTPRINT_SYSTEM_TYPES


@lru_cache(maxsize=1)
def _settlement_subtypes() -> frozenset[str]:
    entry = WorldLocationTypeRegistry.canonical_engine().entry_for("settlement")
    if entry is None:
        return frozenset()
    return frozenset(s.system_subtype for s in entry.subtypes)


@lru_cache(maxsize=1)
def _city_size_tokens() -> frozenset[str]:
    return frozenset(e.system_size for e in WorldCitySizeRegistry.canonical_defaults().root)


def uses_settlement_meter_footprint(
    *,
    system_location_type: str | None,
    system_location_subtype: str | None = None,
    system_city_size: str | None = None,
) -> bool:
    """True when territory uses settlement assembler meter rect, not pin box."""
    if system_city_size:
        token = system_city_size.strip().lower()
        if token in _city_size_tokens() or token in _LEGACY_SIZE_ALIASES:
            return True
    loc_type = (system_location_type or "").strip().lower()
    if loc_type in _footprint_system_types():
        return True
    subtype = (system_location_subtype or "").strip().lower()
    if subtype and (subtype in _settlement_subtypes() or subtype in _city_size_tokens()):
        return True
    return False


def named_location_uses_settlement_meter_footprint(location: object) -> bool:
    """``NamedLocation`` / bundle row — typed fields via getattr for tests."""
    return uses_settlement_meter_footprint(
        system_location_type=getattr(location, "system_location_type", None),
        system_location_subtype=getattr(location, "system_location_subtype", None),
        system_city_size=getattr(location, "system_city_size", None),
    )
