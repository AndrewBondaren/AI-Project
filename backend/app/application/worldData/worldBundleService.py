"""WorldBundleService — import/export connections (D HY-0b)."""

from dataclasses import asdict

from fastapi import HTTPException

from app.api.schemas.imports import ImportResult
from app.application.jsonValidation.bundle import normalize_bundle_connections
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError, import_validation_http_detail
from app.application.worldData.bundleRemapService import remap_bundle
from app.application.worldData.connectionGraphService import ConnectionGraphService
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
        connection_graph_service: ConnectionGraphService,
    ) -> None:
        self._db              = db
        self._world           = world_service
        self._races           = race_service
        self._perks           = perk_service
        self._locations       = location_service
        self._map_cells       = map_cell_service
        self._states          = state_service
        self._connections     = connection_graph_service

    async def export(self, world_uid: str) -> dict:
        world     = await self._world.get_by_id(world_uid)
        races     = await self._races.get_all(world_uid)
        perks     = await self._perks.get_all(world_uid)
        locations = await self._locations.get_all(world_uid)
        map_cells = await self._map_cells.get_all(world_uid)
        states    = await self._states.get_all(world_uid)
        nodes     = await self._connections.export_nodes(world_uid)
        edges     = await self._connections.export_edges(world_uid)
        return {
            "world":             asdict(world),
            "races":             [asdict(r) for r in races],
            "perks":             [asdict(p) for p in perks],
            "locations":         [asdict(l) for l in locations],
            "map_cells":         [asdict(c) for c in map_cells],
            "states":            [asdict(s) for s in states],
            "connection_nodes":  nodes,
            "connection_edges":  edges,
        }

    async def import_bundle(self, data: dict) -> tuple[dict[str, ImportResult], bool]:
        if "world" not in data:
            raise HTTPException(status_code=422, detail="Bundle must contain 'world' key")

        world_data = data["world"]
        world_uid  = world_data.get("world_uid")
        if not world_uid:
            raise HTTPException(status_code=422, detail="world.world_uid is required")

        existing = await self._world.find_by_id(world_uid)
        if existing is not None:
            version_n = await self._world.next_version_number(existing.name)
            data      = remap_bundle(data, version_n, self._world.strip_version_suffix)
            world_uid = data["world"]["world_uid"]

        try:
            data = {**data, "world": normalize_world(data["world"])}
            data = normalize_bundle_connections(data)
        except ImportValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=import_validation_http_detail(exc),
            ) from exc

        results: dict[str, ImportResult] = {}
        rolled_back = False
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

                if "connection_nodes" in data:
                    results["connection_nodes"] = await self._connections.import_nodes(
                        world_uid, data["connection_nodes"],
                    )
                if "connection_edges" in data:
                    results["connection_edges"] = await self._connections.import_edges(
                        world_uid, data["connection_edges"],
                    )

                if any(r.failed > 0 for r in results.values()):
                    raise _ImportFailed()
        except _ImportFailed:
            rolled_back = True

        return results, rolled_back
