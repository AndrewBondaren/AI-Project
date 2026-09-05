"""SQL identity overlay on pack ``locations_index`` pins — tz_pack_ascii_render L0 identity."""

from __future__ import annotations

from collections.abc import Sequence

from app.application.worldData.render.mapSymbols import SETTLEMENT_FOOTPRINT_SYMBOL
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.db.models.namedLocation import NamedLocation


def overlay_location_pins(
    index: LocationsIndexWire,
    locations: Sequence[NamedLocation],
) -> LocationsIndexWire:
    """Copy SQL type/subtype/size/name onto pack pins. Same length and order."""
    by_uid = {loc.location_uid: loc for loc in locations}
    pins: list[LocationsIndexPin] = []
    for pin in index.locations:
        loc = by_uid.get(pin.location_uid)
        if loc is None:
            pins.append(pin)
            continue
        pins.append(
            pin.model_copy(
                update={
                    "system_location_type": loc.system_location_type,
                    "system_location_subtype": loc.system_location_subtype,
                    "system_city_size": loc.system_city_size,
                    "display_name": loc.display_name,
                },
            ),
        )
    return LocationsIndexWire(locations=pins)


def pin_at(
    pins: Sequence[LocationsIndexPin] | None,
    index: int | None,
) -> LocationsIndexPin | None:
    if pins is None or index is None:
        return None
    if 0 <= index < len(pins):
        return pins[index]
    return None


def l0_settlement_glyph(
    pin: LocationsIndexPin | None,
    *,
    location_types: WorldLocationTypeRegistry | None = None,
) -> str:
    """Footprint letter from subtype ``l0_map_symbol``; unknown site → urban ``u``."""
    engine = WorldLocationTypeRegistry.canonical_engine()
    registries: list[WorldLocationTypeRegistry] = []
    if location_types is not None:
        registries.append(location_types)
    registries.append(engine)
    loc_type = ""
    subtype = ""
    if pin is not None:
        loc_type = (pin.system_location_type or "").strip()
        subtype = (pin.system_location_subtype or "").strip()
    if subtype:
        type_keys = [loc_type, "settlement"] if loc_type else ["settlement"]
        for registry in registries:
            for key in type_keys:
                if not key:
                    continue
                entry = registry.subtype_for(key, subtype)
                if entry is not None and entry.l0_map_symbol:
                    return entry.l0_map_symbol
    return SETTLEMENT_FOOTPRINT_SYMBOL
