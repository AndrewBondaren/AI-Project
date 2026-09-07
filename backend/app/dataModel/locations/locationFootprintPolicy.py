"""Settlement vs pin territory — type/subtype, not size rank (LOC-T-2)."""

from __future__ import annotations

from functools import lru_cache

from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry

_LEGACY_FOOTPRINT_SYSTEM_TYPES = frozenset({"city"})


@lru_cache(maxsize=1)
def _footprint_system_types() -> frozenset[str]:
    return frozenset({"settlement", "district"}) | _LEGACY_FOOTPRINT_SYSTEM_TYPES


@lru_cache(maxsize=1)
def _settlement_subtypes() -> frozenset[str]:
    entry = WorldLocationTypeRegistry.canonical_engine().entry_for(
        WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT,
    )
    if entry is None:
        return frozenset()
    return frozenset(s.system_subtype for s in entry.subtypes)


def uses_settlement_meter_footprint(
    *,
    system_location_type: str | None,
    system_location_subtype: str | None = None,
) -> bool:
    """True when territory uses settlement assembler meter rect, not pin box.

    Size rank (``small`` / ``medium`` / ``large``) is not a settlement signal.
    """
    loc_type = (system_location_type or "").strip().lower()
    if loc_type in _footprint_system_types():
        return True
    subtype = (system_location_subtype or "").strip().lower()
    if subtype and subtype in _settlement_subtypes():
        return True
    return False


def named_location_uses_settlement_meter_footprint(location: object) -> bool:
    """``NamedLocation`` / bundle row — typed fields via getattr for tests."""
    return uses_settlement_meter_footprint(
        system_location_type=getattr(location, "system_location_type", None),
        system_location_subtype=getattr(location, "system_location_subtype", None),
    )


def is_settlement_map_site(
    *,
    system_location_type: str | None,
    system_location_subtype: str | None = None,
) -> bool:
    """L0 city footprint: settlement root, not district/building/room or geography."""
    if not uses_settlement_meter_footprint(
        system_location_type=system_location_type,
        system_location_subtype=system_location_subtype,
    ):
        return False
    loc_type = (system_location_type or "").strip().lower()
    if not loc_type:
        return True
    engine = WorldLocationTypeRegistry.canonical_engine()
    entry = engine.entry_for(loc_type)
    if entry is None:
        return True
    settlement = engine.entry_for(WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT)
    if settlement is not None and entry.system_type == settlement.system_type:
        return True
    nested = {
        e.system_type
        for key in (
            WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT,
            WorldLocationTypeRegistry.SYSTEM_TYPE_DISTRICT,
            WorldLocationTypeRegistry.SYSTEM_TYPE_BUILDING,
        )
        if (e := engine.entry_for(key)) is not None
    }
    return not any(p in nested for p in (entry.parent_types or []) if p)


def named_location_is_settlement_map_site(location: object) -> bool:
    return is_settlement_map_site(
        system_location_type=getattr(location, "system_location_type", None),
        system_location_subtype=getattr(location, "system_location_subtype", None),
    )
