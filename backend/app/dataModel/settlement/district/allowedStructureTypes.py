"""CITY-T-2a — ``allowed_structure_types`` null / [] / list + like/strict."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.dataModel.structure.enums.buildingPurpose import (
    BuildingPurpose,
    BuildingPurposeMatch,
    coerce_purpose_list,
    coerce_purpose_match,
)


def allowed_fill_structure_types(
    allowed: list[BuildingPurpose] | list[str] | None,
    catalog_structure_types: Iterable[str],
) -> tuple[str, ...]:
    """Fill purposes for packing (required is separate).

    ``None`` / omit → catalog purpose keys, sorted.
    ``[]`` → no fill (required / pins only).
    list → those purposes (unknown dropped; not in catalog dropped).
    """
    catalog = set(catalog_structure_types)
    if allowed is None:
        return tuple(sorted(catalog))
    parsed = coerce_purpose_list(allowed, empty_as_house=False)
    return tuple(str(purpose) for purpose in parsed if str(purpose) in catalog)


def allowed_match_mode(raw: object) -> BuildingPurposeMatch:
    return coerce_purpose_match(raw)


def district_hosts_purpose(
    allowed: Sequence[BuildingPurpose] | None,
    purpose: BuildingPurpose | str,
) -> bool:
    """Whether this district may host a settlement-required purpose.

    Omit / ``None`` → all catalog purposes (unrestricted fill).
    ``[]`` → pins only, not a host.
    list → membership of that purpose key (not like/strict on a drawing).
    """
    parsed = (
        purpose
        if isinstance(purpose, BuildingPurpose)
        else BuildingPurpose.from_wire(purpose)
    )
    if parsed is None:
        return False
    if allowed is None:
        return True
    allowed_set: set[BuildingPurpose] = set()
    for item in allowed:
        parsed_item = (
            item
            if isinstance(item, BuildingPurpose)
            else BuildingPurpose.from_wire(item)
        )
        if parsed_item is not None:
            allowed_set.add(parsed_item)
    return parsed in allowed_set
