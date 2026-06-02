import copy
import uuid
from dataclasses import asdict

from fastapi import HTTPException

from app.api.schemas.imports import ImportResult
from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.namedLocationService import NamedLocationService
from app.application.worldData.raceService import RaceService
from app.application.worldData.stateService import StateService
from app.application.worldData.worldPerkService import WorldPerkService
from app.application.worldData.worldService import WorldService
from app.db.database import Database
from app.utils.graph import topo_sort


class _ImportFailed(Exception):
    pass


class WorldBundleService:

    def __init__(
        self,
        db: Database,
        world_service: WorldService,
        race_service: RaceService,
        perk_service: WorldPerkService,
        location_service: NamedLocationService,
        map_cell_service: MapCellService,
        state_service: StateService,
    ) -> None:
        self._db        = db
        self._world     = world_service
        self._races     = race_service
        self._perks     = perk_service
        self._locations = location_service
        self._map_cells = map_cell_service
        self._states    = state_service

    async def export(self, world_uid: str) -> dict:
        world     = await self._world.get_by_id(world_uid)
        races     = await self._races.get_all(world_uid)
        perks     = await self._perks.get_all(world_uid)
        locations = await self._locations.get_all(world_uid)
        map_cells = await self._map_cells.get_all(world_uid)
        states    = await self._states.get_all(world_uid)
        return {
            "world":     asdict(world),
            "races":     [asdict(r) for r in races],
            "perks":     [asdict(p) for p in perks],
            "locations": [asdict(l) for l in locations],
            "map_cells": [asdict(c) for c in map_cells],
            "states":    [asdict(s) for s in states],
        }

    async def import_bundle(self, data: dict) -> dict[str, ImportResult]:
        if "world" not in data:
            raise HTTPException(status_code=422, detail="Bundle must contain 'world' key")

        world_data = data["world"]
        world_uid  = world_data.get("world_uid")
        if not world_uid:
            raise HTTPException(status_code=422, detail="world.world_uid is required")

        existing = await self._world.find_by_id(world_uid)
        if existing is not None:
            version_n = await self._world.next_version_number(existing.name)
            data      = _remap_bundle(data, version_n, self._world.strip_version_suffix)
            world_uid = data["world"]["world_uid"]

        results: dict[str, ImportResult] = {}
        try:
            async with self._db.transaction():
                results["world"] = await self._world.import_from_json(data["world"])
                if results["world"].failed > 0:
                    raise _ImportFailed()

                sections = {
                    "races":     self._races,
                    "perks":     self._perks,
                    "states":    self._states,
                    "locations": self._locations,
                    "map_cells": self._map_cells,
                }
                for key, svc in sections.items():
                    if key in data:
                        section_data = data[key]
                        if key == "locations":
                            section_data = topo_sort(section_data, "location_uid", "parent_location_uid")
                        results[key] = await svc.import_from_json(world_uid, section_data)

                if any(r.failed > 0 for r in results.values()):
                    raise _ImportFailed()
        except _ImportFailed:
            pass

        return results


def _remap_bundle(data: dict, version_n: int, strip_suffix) -> dict:
    """Return a deep copy of the bundle with all UIDs replaced and name versioned."""
    uid_map: dict[str, str] = {}

    def remap(old: str) -> str:
        if old not in uid_map:
            uid_map[old] = str(uuid.uuid4())
        return uid_map[old]

    original_world_uid = data["world"]["world_uid"]
    _PK = {"locations": "location_uid", "states": "state_uid",
           "races": "race_uid", "perks": "perk_uid"}

    remap(original_world_uid)
    for key, pk in _PK.items():
        for item in data.get(key, []):
            remap(item[pk])

    result        = copy.deepcopy(data)
    new_world_uid = uid_map[original_world_uid]

    w          = result["world"]
    w["world_uid"] = new_world_uid
    w["name"]      = f"{strip_suffix(w.get('name', ''))} v{version_n}"

    # Simple entities: remap own pk + world_uid
    for key, pk in {"states": "state_uid", "races": "race_uid", "perks": "perk_uid"}.items():
        for item in result.get(key, []):
            item[pk]         = uid_map[item[pk]]
            item["world_uid"] = new_world_uid

    # Locations: own pk + world_uid + cross-references
    for loc in result.get("locations", []):
        loc["location_uid"] = uid_map[loc["location_uid"]]
        loc["world_uid"]    = new_world_uid
        if loc.get("parent_location_uid") in uid_map:
            loc["parent_location_uid"] = uid_map[loc["parent_location_uid"]]
        if loc.get("state_uid") in uid_map:
            loc["state_uid"] = uid_map[loc["state_uid"]]

    # map_cells: no own pk, only foreign references
    for c in result.get("map_cells", []):
        c["world_uid"] = new_world_uid
        if c.get("location_uid") in uid_map:
            c["location_uid"] = uid_map[c["location_uid"]]

    return result
