"""Build locations_index.json from NamedLocation rows — WP-9 / CL-PACK-3."""

from __future__ import annotations

from app.application.worldData.settlementMapOccupancy import occupancy_locations
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def build_locations_index(
    locations: list[NamedLocation],
    world: World | None = None,
) -> LocationsIndexWire:
    rows = occupancy_locations(world, locations) if world is not None else locations
    pins: list[LocationsIndexPin] = []
    for loc in rows:
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
                system_location_subtype=loc.system_location_subtype,
                system_city_size=loc.system_city_size,
            ),
        )
    return LocationsIndexWire(locations=pins)
