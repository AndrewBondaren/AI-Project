"""Geographic mountain / peak anchors → Spec origins (not disk paint / not declare)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.dataModel.locations.enums.geographicSubtype import (
    GEOGRAPHIC_LOCATION_TYPE,
    GeographicSubtype,
)

if TYPE_CHECKING:
    from app.db.models.namedLocation import NamedLocation

_ANCHOR_SUBTYPES = frozenset({GeographicSubtype.MOUNTAIN, GeographicSubtype.PEAK})


def anchor_mountain_locations(
    locations: list[NamedLocation],
) -> list[NamedLocation]:
    """Geographic mountain / peak anchors with map coords (anchor Spec source)."""
    out: list[NamedLocation] = []
    for loc in locations:
        if loc.system_location_type != GEOGRAPHIC_LOCATION_TYPE:
            continue
        subtype = GeographicSubtype.from_wire(getattr(loc, "system_location_subtype", None))
        if subtype not in _ANCHOR_SUBTYPES:
            continue
        if loc.map_x is None or loc.map_y is None:
            continue
        out.append(loc)
    return out


# Back-compat alias during rename (Q16)
declare_mountain_locations = anchor_mountain_locations
