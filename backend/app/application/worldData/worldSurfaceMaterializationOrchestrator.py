"""World pack materialization facade — thin entry for debug HTTP / scripts.

Legacy map_cells ``materialize_surface_stack`` removed; use ``materialize_pack_light``.
"""

from __future__ import annotations

from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.pack.bake.packMaterializationOrchestrator import (
    PackMaterializationOrchestrator,
)
from app.application.worldData.materializationContext import (
    MaterializationContext,
    MaterializationJobReport,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class WorldSurfaceMaterializationOrchestrator:
    """Pack-only surface materialization entry (L0 light + entry refine)."""

    def __init__(self, pack: PackMaterializationOrchestrator) -> None:
        self._pack = pack

    async def materialize_pack_light(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        pack_writer,
        *,
        max_tiles: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        heading_dx: int | None = None,
        heading_dy: int | None = None,
        pack_orchestrator: PackMaterializationOrchestrator | None = None,
    ) -> MaterializationJobReport:
        orch = pack_orchestrator if pack_orchestrator is not None else self._pack
        return await orch.materialize_light_pack(
            world_uid, world, locations, pack_writer, ctx,
            max_tiles=max_tiles,
            nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
            anchor_x=anchor_x, anchor_y=anchor_y,
            heading_dx=heading_dx, heading_dy=heading_dy,
        )
