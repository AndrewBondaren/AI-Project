from dataclasses import asdict

from fastapi import HTTPException

from app.api.schemas.imports import ImportResult
from app.application.worldData.namedLocationService import NamedLocationService
from app.application.worldData.raceService import RaceService
from app.application.worldData.worldPerkService import WorldPerkService
from app.application.worldData.worldService import WorldService


class WorldBundleService:

    def __init__(
        self,
        world_service: WorldService,
        race_service: RaceService,
        perk_service: WorldPerkService,
        location_service: NamedLocationService,
    ) -> None:
        self._world = world_service
        self._races = race_service
        self._perks = perk_service
        self._locations = location_service

    async def export(self, world_uid: str) -> dict:
        world = await self._world.get_by_id(world_uid)
        races = await self._races.get_all(world_uid)
        perks = await self._perks.get_all(world_uid)
        locations = await self._locations.get_all(world_uid)
        return {
            "world": asdict(world),
            "races": [asdict(r) for r in races],
            "perks": [asdict(p) for p in perks],
            "locations": [asdict(l) for l in locations],
        }

    async def import_bundle(self, data: dict) -> dict[str, ImportResult]:
        if "world" not in data:
            raise HTTPException(status_code=422, detail="Bundle must contain 'world' key")

        world_data = data["world"]
        world_uid = world_data.get("world_uid")
        if not world_uid:
            raise HTTPException(status_code=422, detail="world.world_uid is required")

        results: dict[str, ImportResult] = {}
        results["world"] = await self._world.import_from_json(world_data)

        if results["world"].failed > 0:
            return results

        if "races" in data:
            results["races"] = await self._races.import_from_json(world_uid, data["races"])
        if "perks" in data:
            results["perks"] = await self._perks.import_from_json(world_uid, data["perks"])
        if "locations" in data:
            results["locations"] = await self._locations.import_from_json(world_uid, data["locations"])

        return results
