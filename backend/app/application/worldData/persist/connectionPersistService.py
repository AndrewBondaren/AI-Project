import logging
from dataclasses import dataclass, field

from app.api.schemas.imports import ImportResult
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionEdgeCell import ConnectionEdgeCell
from app.db.models.connectionNode import ConnectionNode
from app.db.repositories.iConnectionEdgeCellRepository import IConnectionEdgeCellRepository
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPersistResult:
    nodes:      ImportResult
    edges:      ImportResult
    edge_cells: ImportResult = field(default_factory=lambda: ImportResult(0, 0, 0))

    def to_dict(self) -> dict:
        return {
            "nodes":      self.nodes.to_dict(),
            "edges":      self.edges.to_dict(),
            "edge_cells": self.edge_cells.to_dict(),
        }


class ConnectionPersistService:

    def __init__(
        self,
        node_repo:      IConnectionNodeRepository,
        edge_repo:      IConnectionEdgeRepository,
        edge_cell_repo: IConnectionEdgeCellRepository,
    ) -> None:
        self._node_repo      = node_repo
        self._edge_repo      = edge_repo
        self._edge_cell_repo = edge_cell_repo

    async def persist_graph(
        self,
        nodes:      list[ConnectionNode],
        edges:      list[ConnectionEdge],
        edge_cells: list[ConnectionEdgeCell] | None = None,
    ) -> ConnectionPersistResult:
        node_count = await self._node_repo.upsert_bulk(nodes)
        edge_count = await self._edge_repo.upsert_bulk(edges)

        cell_count = 0
        if edge_cells:
            cell_count = await self._edge_cell_repo.upsert_bulk(edge_cells)

        logger.info(
            "ConnectionPersistService | nodes=%d/%d edges=%d/%d edge_cells=%d",
            node_count, len(nodes),
            edge_count, len(edges),
            cell_count,
        )

        return ConnectionPersistResult(
            nodes=ImportResult(total=len(nodes), succeeded=node_count, failed=0),
            edges=ImportResult(total=len(edges), succeeded=edge_count, failed=0),
            edge_cells=ImportResult(total=len(edge_cells or []), succeeded=cell_count, failed=0),
        )
