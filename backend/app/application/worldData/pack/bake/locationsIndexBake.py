"""Build locations_index.json from NamedLocation rows — WP-9 / CL-PACK-3."""

from __future__ import annotations

from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.db.models.namedLocation import NamedLocation


def build_locations_index(locations: list[NamedLocation]) -> LocationsIndexWire:
    pins: list[LocationsIndexPin] = []
    for loc in locations:
        if loc.map_x is None or loc.map_y is None:
            continue
        pins.append(
            LocationsIndexPin(
                location_uid=loc.location_uid,
                map_x=loc.map_x,
                map_y=loc.map_y,
                map_z=0 if loc.map_z is None else loc.map_z,
                display_name=loc.display_name,
                system_location_type=loc.system_location_type,
            ),
        )
    return LocationsIndexWire(locations=pins)
