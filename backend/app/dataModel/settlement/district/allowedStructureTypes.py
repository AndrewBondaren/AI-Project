"""CITY-T-2a — ``allowed_structure_types`` null / [] / list + like/strict.

Filter tokens are leaves and/or families (tz_building_generator.md §2.1).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.dataModel.structure.enums.buildingPurpose import (
    AllowedToken,
    BuildingPurpose,
    BuildingPurposeMatch,
    coerce_purpose_match,
    expand_allowed,
)


def _enabled_keys(
    enabled: Iterable[BuildingPurpose] | None,
) -> set[str] | None:
    if enabled is None:
        return None
    return {str(purpose) for purpose in enabled}


def allowed_fill_structure_types(
    allowed: Sequence[AllowedToken | str] | None,
    catalog_structure_types: Iterable[str],
    enabled: Iterable[BuildingPurpose] | None = None,
) -> tuple[str, ...]:
    """Fill purposes for packing (required is separate).

    ``None`` / omit → catalog purpose keys ∩ enabled (enabled omit → catalog).
    ``[]`` → no fill (required / pins only).
    list → expand families, then ∩ catalog ∩ enabled.
    """
    catalog = set(catalog_structure_types)
    live = _enabled_keys(enabled)
    if allowed is None:
        keys = catalog if live is None else catalog & live
        return tuple(sorted(keys))
    parsed = expand_allowed(allowed)
    return tuple(
        str(purpose)
        for purpose in parsed
        if str(purpose) in catalog and (live is None or str(purpose) in live)
    )


def allowed_match_mode(raw: object) -> BuildingPurposeMatch:
    return coerce_purpose_match(raw)


def district_hosts_purpose(
    allowed: Sequence[AllowedToken | str] | None,
    purpose: BuildingPurpose | str,
    enabled: Iterable[BuildingPurpose] | None = None,
) -> bool:
    """Whether this district may host a settlement-required purpose.

    Omit / ``None`` → all enabled catalog purposes (unrestricted fill).
    ``[]`` → pins only, not a host.
    list → leaf or family; family expands before membership.
    ``enabled`` (world packs) further restricts; omit enabled → no pack filter.
    """
    parsed = (
        purpose
        if isinstance(purpose, BuildingPurpose)
        else BuildingPurpose.from_wire(purpose)
    )
    if parsed is None:
        return False
    if enabled is not None and parsed not in set(enabled):
        return False
    if allowed is None:
        return True
    return parsed in expand_allowed(allowed)
