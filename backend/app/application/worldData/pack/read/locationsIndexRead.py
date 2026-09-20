"""Read pack ``locations_index.json`` — occupancy winners on the map (LOC-T-3 / WP-9)."""

from __future__ import annotations

import json

from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire


def load_locations_index(paths: WorldPackPaths) -> LocationsIndexWire | None:
    path = paths.locations_index_path()
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return LocationsIndexWire.model_validate(raw)


def location_uids_in_pack_index(paths: WorldPackPaths) -> frozenset[str]:
    index = load_locations_index(paths)
    if index is None:
        return frozenset()
    return frozenset(pin.location_uid for pin in index.locations)


def location_uid_in_pack_index(paths: WorldPackPaths, location_uid: str) -> bool:
    index = load_locations_index(paths)
    if index is None:
        return False
    return index.contains(location_uid)
