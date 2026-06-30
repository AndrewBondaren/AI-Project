"""Hydrology generator orchestrator stub — D HY-1e."""

from __future__ import annotations

import logging

from app.application.worldData.generators.terrain.hydrology.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from app.application.worldData.generators.terrain.hydrology.types import (
    HydrologyMasterInput,
    HydrologyResult,
    HydrologyScope,
    resolve_scopes,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


class HydrologyGeneratorService:
    """Pure generator — mutates heightmap in later phases; stub returns empty result."""

    def apply(
        self,
        world: World,
        locations: list[NamedLocation],
        heightmap: SurfaceHeightmap,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        scopes: frozenset[HydrologyScope] | None = None,
        master: HydrologyMasterInput | None = None,
    ) -> HydrologyResult:
        nodes = nodes or []
        edges = edges or []
        inp = master or build_hydrology_master_input(
            world, locations, nodes, edges, scopes=scopes,
        )

        if not inp.hydrology_enabled:
            logger.debug("HydrologyGeneratorService | skip disabled world=%s", world.world_uid)
            return HydrologyResult()

        active = resolve_scopes(inp.scopes)
        logger.info(
            "HydrologyGeneratorService | stub world=%s scopes=%s nodes=%d edges=%d",
            world.world_uid,
            sorted(s.value for s in active),
            len(inp.connection_graph.nodes),
            len(inp.connection_graph.edges),
        )
        return HydrologyResult()
