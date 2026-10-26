"""Build locations_index.json from NamedLocation rows — WP-9 / CL-PACK-3."""

from __future__ import annotations

from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.sourceValidation import validate_reference_value
from app.application.jsonValidation.worldRow import location_types
from app.application.worldData.locations.locationPayloadAccess import settlement_payload

from app.application.worldData.locations.settlementMapOccupancy import occupancy_locations
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    LocationTypeKey, WorldLocationTypeRegistry,
)
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def build_locations_index(
    locations: list[NamedLocation],
    world: World | None = None,
) -> LocationsIndexWire:
    """Validate new pin types against the resolved world registry (REF-W).

    World-less callers use engine types. Historical pack reads never use this
    builder and therefore do not recheck membership in today's registry.
    """
    registry = location_types(world) if world is not None else WorldLocationTypeRegistry.canonical_engine()
    references = WorldRegistryIndex(registry_vocabularies={
        WorldLocationTypeRegistry: frozenset(entry.system_type for entry in registry.root),
    })
    rows = occupancy_locations(world, locations) if world is not None else locations
    pins: list[LocationsIndexPin] = []
    for loc in rows:
        if loc.map_x is None or loc.map_y is None:
            continue
        ctx = ResolveContext(path_prefix=("locations_index", "locations", len(pins)))
        validate_reference_value(
            None, LocationTypeKey, loc.system_location_type, ctx,
            ctx.path_prefix + ("system_location_type",), references,
        )
        pins.append(
            LocationsIndexPin(
                location_uid=loc.location_uid,
                map_x=loc.map_x,
                map_y=loc.map_y,
                map_z=0 if loc.map_z is None else loc.map_z,
                display_name=loc.display_name,
                system_location_type=loc.system_location_type,
                system_location_subtype=loc.system_location_subtype,
                system_city_size=settlement_payload(loc).system_city_size,
            ),
        )
    return LocationsIndexWire(locations=pins)
