"""Resolve footprint multiplier as ``(subtype, size)`` — tz_locations.md LOC-T-2.

Consumers call this helper; they do not keep a parallel metre table.
"""

from __future__ import annotations

from app.dataModel.locations.locationType.locationTypeSubtypeEntry import LocationTypeSubtypeEntry
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
    WorldSettlementSizeRegistry,
)

_CODE_DUPLICATE = "DUPLICATE_VALUE"
_CODE_MISSING_TABLE = "MISSING_FOOTPRINT_BY_SIZE"
_CODE_MISSING_RANK = "MISSING_FOOTPRINT_RANK"
_CODE_MISSING_SUBTYPE = "MISSING_SETTLEMENT_SUBTYPE"
_CODE_INVARIANT = "VILLAGE_CITY_FOOTPRINT"
_CODE_MORPHOLOGY_KEY = "SIZE_KEY_IS_MORPHOLOGY"


class SettlementFootprintError(ValueError):
    """Typed failure for footprint resolve / size-registry import checks."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def settlement_morphology_keys(
    location_types: WorldLocationTypeRegistry,
) -> frozenset[str]:
    """``system_subtype`` keys under settlement (engine ⊕ world)."""
    entry = location_types.entry_for(WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT)
    if entry is None:
        return frozenset()
    return frozenset(s.system_subtype.strip().lower() for s in entry.subtypes if s.system_subtype)


def _subtype_entry(
    location_types: WorldLocationTypeRegistry,
    subtype: str,
) -> LocationTypeSubtypeEntry | None:
    key = (subtype or "").strip()
    if not key:
        return None
    found = location_types.subtype_for(
        WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT, key,
    )
    if found is not None:
        return found
    for type_entry in location_types.root:
        found = location_types.subtype_for(type_entry.system_type, key)
        if found is not None:
            return found
    return None


def _engine_morphology_key(system_subtype: str) -> str:
    engine = WorldLocationTypeRegistry.canonical_engine()
    entry = engine.subtype_for(
        WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT, system_subtype,
    )
    if entry is None:
        raise SettlementFootprintError(
            f"engine settlement subtype {system_subtype!r} missing",
            code=_CODE_MISSING_SUBTYPE,
        )
    return entry.system_subtype


def resolve_settlement_footprint_multiplier(
    subtype: str | None,
    size: str | None,
    location_types: WorldLocationTypeRegistry,
    size_registry: WorldSettlementSizeRegistry,
) -> float:
    """Metres factor for ``footprint_by_size[subtype][size]``.

    Omit size → canonical medium. Unknown rank → medium (log at jsonValidation helper).
    """
    sub = (subtype or "").strip()
    raw_size = (size or "").strip() if isinstance(size, str) else ""
    if sub and raw_size and sub.lower() == raw_size.lower():
        raise SettlementFootprintError(
            f"duplicate value: subtype and size are both {sub!r}",
            code=_CODE_DUPLICATE,
        )
    size_key = size_registry.resolve_system_size(raw_size or None)
    if not sub:
        raise SettlementFootprintError(
            "settlement subtype required for footprint",
            code=_CODE_MISSING_SUBTYPE,
        )
    entry = _subtype_entry(location_types, sub)
    if entry is None or not entry.footprint_by_size:
        raise SettlementFootprintError(
            f"no footprint_by_size for subtype {sub!r}",
            code=_CODE_MISSING_TABLE,
        )
    if size_key not in entry.footprint_by_size:
        size_key = WorldSettlementSizeRegistry.default_system_size()
    if size_key not in entry.footprint_by_size:
        raise SettlementFootprintError(
            f"no footprint_by_size[{sub!r}][{size_key!r}]",
            code=_CODE_MISSING_RANK,
        )
    return float(entry.footprint_by_size[size_key])


def village_city_footprint_invariant_holds(
    location_types: WorldLocationTypeRegistry,
    size_registry: WorldSettlementSizeRegistry,
) -> bool:
    """``footprint(city, small) > footprint(village, large)`` on the given registries."""
    canon = WorldSettlementSizeRegistry.canonical_defaults()
    small = canon.root[0].system_size
    large = canon.root[-1].system_size
    village = _engine_morphology_key("village")
    city = _engine_morphology_key("city")
    city_small = resolve_settlement_footprint_multiplier(
        city, small, location_types, size_registry,
    )
    village_large = resolve_settlement_footprint_multiplier(
        village, large, location_types, size_registry,
    )
    return city_small > village_large


def settlement_size_registry_issues(
    location_types: WorldLocationTypeRegistry,
    size_registry: WorldSettlementSizeRegistry,
) -> list[tuple[str, str]]:
    """Import checks: morphology collision, missing metre rows, village≺city.

    Returns ``(code, message)`` pairs.
    """
    issues: list[tuple[str, str]] = []
    morph = settlement_morphology_keys(location_types)
    for entry in size_registry.root:
        key = entry.system_size.strip().lower()
        if key in morph:
            issues.append((
                _CODE_MORPHOLOGY_KEY,
                f"settlement size {entry.system_size!r} collides with morphology",
            ))
    settlement = location_types.entry_for(WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT)
    if settlement is not None:
        ranks = [e.system_size for e in size_registry.root]
        for sub in settlement.subtypes:
            table = sub.footprint_by_size
            if not table:
                issues.append((
                    _CODE_MISSING_TABLE,
                    f"settlement subtype {sub.system_subtype!r} has no footprint_by_size",
                ))
                continue
            for rank in ranks:
                if rank not in table:
                    issues.append((
                        _CODE_MISSING_RANK,
                        f"footprint_by_size[{sub.system_subtype!r}] missing rank {rank!r}",
                    ))
    try:
        if not village_city_footprint_invariant_holds(location_types, size_registry):
            issues.append((
                _CODE_INVARIANT,
                "footprint(city, small) must exceed footprint(village, large)",
            ))
    except SettlementFootprintError as exc:
        issues.append((exc.code, str(exc)))
    return issues
