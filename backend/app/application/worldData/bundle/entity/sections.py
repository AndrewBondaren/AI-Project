"""Entity section handlers — tz_world_bundle.md."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.application.importResult import ImportResult
from app.application.worldData.bundle.errors import BundleValidationError
from app.application.worldData.connectionGraphService import ConnectionGraphService
from app.application.worldData.namedLocationService import NamedLocationService
from app.application.worldData.stateService import StateService
from app.application.worldData.worldService import WorldService
from app.dataModel.worldBundle.bundleSections import BundleSection
from app.db.models.world import World
from app.utils.graph import topo_sort


class WorldSectionHandler:
    key = BundleSection.WORLD

    def __init__(self, world_service: WorldService) -> None:
        self._worlds = world_service

    async def export_section(
        self, world_uid: str, *, world: World | None = None,
    ) -> dict:
        w = world or await self._worlds.get_by_id(world_uid)
        return asdict(w)

    async def import_section(self, world_uid: str, data: Any) -> ImportResult:
        if not isinstance(data, dict):
            raise BundleValidationError("world section must be an object")
        return await self._worlds.import_from_json(data)


class StatesSectionHandler:
    key = BundleSection.STATES

    def __init__(self, state_service: StateService) -> None:
        self._states = state_service

    async def export_section(
        self, world_uid: str, *, world: World | None = None,
    ) -> list[dict]:
        return [asdict(s) for s in await self._states.get_all(world_uid)]

    async def import_section(self, world_uid: str, data: Any) -> ImportResult:
        if not isinstance(data, list):
            raise BundleValidationError("states section must be an array")
        return await self._states.import_from_json(world_uid, data)


class LocationsSectionHandler:
    key = BundleSection.LOCATIONS

    def __init__(self, location_service: NamedLocationService) -> None:
        self._locations = location_service

    async def export_section(
        self, world_uid: str, *, world: World | None = None,
    ) -> list[dict]:
        return [asdict(loc) for loc in await self._locations.get_all(world_uid)]

    async def import_section(self, world_uid: str, data: Any) -> ImportResult:
        if not isinstance(data, list):
            raise BundleValidationError("locations section must be an array")
        section_data = topo_sort(data, "location_uid", "parent_location_uid")
        return await self._locations.import_from_json(world_uid, section_data)


class ConnectionNodesSectionHandler:
    key = BundleSection.CONNECTION_NODES

    def __init__(self, connections: ConnectionGraphService) -> None:
        self._connections = connections

    async def export_section(
        self, world_uid: str, *, world: World | None = None,
    ) -> list:
        return await self._connections.export_nodes(world_uid)

    async def import_section(self, world_uid: str, data: Any) -> ImportResult:
        if not isinstance(data, list):
            raise BundleValidationError("connection_nodes section must be an array")
        return await self._connections.import_nodes(world_uid, data)


class ConnectionEdgesSectionHandler:
    key = BundleSection.CONNECTION_EDGES

    def __init__(self, connections: ConnectionGraphService) -> None:
        self._connections = connections

    async def export_section(
        self, world_uid: str, *, world: World | None = None,
    ) -> list:
        return await self._connections.export_edges(world_uid)

    async def import_section(self, world_uid: str, data: Any) -> ImportResult:
        if not isinstance(data, list):
            raise BundleValidationError("connection_edges section must be an array")
        return await self._connections.import_edges(world_uid, data)
