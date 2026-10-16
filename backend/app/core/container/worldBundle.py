"""World-bundle wiring: connection graph and world import/export."""

from app.application.worldBundle.registry import build_bundle_handlers
from app.application.worldBundle.connectionGraphService import ConnectionGraphService
from app.application.worldBundle.worldBundleService import WorldBundleService


class WorldBundleWiring:
    """World bundle service and the connection-graph read seam."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._world_bundle_service: WorldBundleService | None = None
        self._connection_graph_service: ConnectionGraphService | None = None

    def connection_graph_service(self) -> ConnectionGraphService:
        if self._connection_graph_service is None:
            self._connection_graph_service = ConnectionGraphService(
                node_repo=self.connection_node_repository(),
                edge_repo=self.connection_edge_repository(),
            )
        return self._connection_graph_service

    def world_bundle_service(self) -> WorldBundleService:
        if self._world_bundle_service is None:
            handlers = build_bundle_handlers(
                world_service=self.world_service(),
                state_service=self.state_service(),
                location_service=self.location_service(),
                connection_graph_service=self.connection_graph_service(),
                race_service=self.race_service(),
                perk_service=self.perk_service(),
            )
            self._world_bundle_service = WorldBundleService(
                db=self._db,
                world_service=self.world_service(),
                handlers=handlers,
                library_archives=self.library_pack_service().archives,
                legacy_migration=self.legacy_world_migration(),
            )
        return self._world_bundle_service
