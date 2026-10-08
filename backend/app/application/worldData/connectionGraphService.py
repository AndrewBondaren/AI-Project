"""Import/export connection_nodes and connection_edges for world bundle (D HY-0b)."""

from dataclasses import asdict

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list, prepare_import_row
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository


class ConnectionGraphService:

    def __init__(
        self,
        node_repo: IConnectionNodeRepository,
        edge_repo: IConnectionEdgeRepository,
    ) -> None:
        self._node_repo = node_repo
        self._edge_repo = edge_repo

    async def get_nodes(self, world_uid: str) -> list[ConnectionNode]:
        return await self._node_repo.get_by_world(world_uid)

    async def get_edges(self, world_uid: str) -> list[ConnectionEdge]:
        return await self._edge_repo.get_by_world(world_uid)

    async def export_nodes(self, world_uid: str) -> list[dict]:
        return [asdict(n) for n in await self.get_nodes(world_uid)]

    async def export_edges(self, world_uid: str) -> list[dict]:
        return [asdict(e) for e in await self.get_edges(world_uid)]

    async def import_nodes(self, world_uid: str, data: list[dict]) -> ImportResult:
        return await import_list(data, lambda row: self.prepare_node(world_uid, row), self._node_repo.upsert, id_key="node_uid")

    @staticmethod
    def prepare_node(world_uid: str, row: dict) -> ConnectionNode:
        return prepare_import_row(ConnectionNode, {**row, "world_uid": world_uid})

    async def import_edges(self, world_uid: str, data: list[dict]) -> ImportResult:
        return await import_list(data, lambda row: self.prepare_edge(world_uid, row), self._edge_repo.upsert, id_key="edge_uid")

    @staticmethod
    def prepare_edge(world_uid: str, row: dict) -> ConnectionEdge:
        # C4: location_uid on edge is draft-only; names live on waypoint nodes.
        cleaned = {k: v for k, v in row.items() if k != "location_uid"}
        return prepare_import_row(ConnectionEdge, {**cleaned, "world_uid": world_uid})
