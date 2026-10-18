"""worldData wiring: domain services, persist, transitions, orchestrators."""

from collections.abc import Mapping, Sequence

from app.application.jsonValidation.worldRow import transition_types
from app.application.worldData.transitions.transitionService import TransitionService
from app.application.worldData.transitions.transitionReadService import BuildingTransitionPackBinding, TransitionReadService
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationLevel import LocationLevel
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iTransitionRepository import TransitionRepositoryContext
from app.db.repositories.sqlite.transitionRepository import SqliteTransitionRepository
from app.db.repositories.sqlite.regionStateRepository import SqliteRegionStateRepository
from app.application.worldData.registries.worldService import WorldService
from app.application.worldData.registries.raceService import RaceService
from app.application.worldData.registries.worldPerkService import WorldPerkService
from app.application.worldData.locations.namedLocationService import NamedLocationService
from app.application.worldData.mapCells.mapCellService import MapCellService
from app.application.worldData.mapCells.bootstrapMapCellWriter import BootstrapMapCellWriter
from app.application.worldData.mapCells.patchStoreService import PatchStoreService
from app.application.worldData.materialize.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.materialize.climateBatchOrchestrator import ClimateBatchOrchestrator
from app.application.worldData.materialize.worldSurfaceMaterializationOrchestrator import (
    WorldSurfaceMaterializationOrchestrator,
)
from app.application.worldData.persist.connectionPersistService import ConnectionPersistService
from app.application.worldData.persist.settlementPersistService import SettlementPersistService
from app.application.worldData.settlementOutdoor.settlementOutdoorOrchestrator import (
    SettlementOutdoorOrchestrator,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import (
    SettlementOutdoorSqlPersist,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.registries.stateService import StateService
from app.application.worldData.registries.seedService import SeedService
from app.application.worldData.pack.bake.packMaterializationOrchestrator import PackMaterializationOrchestrator
from app.application.worldData.pack.refine.entry.entryRefineOrchestrator import EntryRefineOrchestrator
from app.application.worldData.pack.refine.fine.fineTerrainRefineOrchestrator import FineTerrainRefineOrchestrator
from app.dataModel.worldPack.bake.packBakeDefaults import PackBakeDefaults


class WorldDataWiring:
    """World-domain services, persist seams and generation orchestrators."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._world_service: WorldService | None = None
        self._race_service: RaceService | None = None
        self._perk_service: WorldPerkService | None = None
        self._location_service: NamedLocationService | None = None
        self._map_cell_service: MapCellService | None = None
        self._bootstrap_map_cell_writer: BootstrapMapCellWriter | None = None
        self._terrain_batch_orchestrator: TerrainBatchOrchestrator | None = None
        self._climate_batch_orchestrator: ClimateBatchOrchestrator | None = None
        self._surface_materialization_orchestrator: WorldSurfaceMaterializationOrchestrator | None = None
        self._connection_persist_service: ConnectionPersistService | None = None
        self._settlement_persist_service: SettlementPersistService | None = None
        self._settlement_outdoor_orchestrator: SettlementOutdoorOrchestrator | None = None
        self._state_service: StateService | None = None
        self._seed_service: SeedService | None = None
        self._patch_store_service: PatchStoreService | None = None
        self._pack_materialization_orchestrator = None
        self._entry_refine_orchestrator = None

    def world_service(self) -> WorldService:
        if self._world_service is None:
            self._world_service = WorldService(repo=self.world_repository())
        return self._world_service

    def transition_service(
        self, world: World, *, levels: Mapping[str, LocationLevel],
        locations: Mapping[str, NamedLocation], nodes: Mapping[str, ConnectionNode],
    ) -> TransitionService:
        # A fresh world-bound scope prevents reuse of another world's registry/reference snapshot.
        registry = transition_types(world)
        context = TransitionRepositoryContext(world.world_uid, registry, levels, locations, nodes)
        return TransitionService(SqliteTransitionRepository(self._db, context), registry)

    def transition_read_service(
        self, world: World, *, levels: Mapping[str, LocationLevel],
        locations: Mapping[str, NamedLocation], nodes: Mapping[str, ConnectionNode],
        bindings: Sequence[BuildingTransitionPackBinding],
    ) -> TransitionReadService:
        registry = transition_types(world)
        context = TransitionRepositoryContext(world.world_uid, registry, levels, locations, nodes)
        sql = TransitionService(SqliteTransitionRepository(self._db, context), registry)
        return TransitionReadService(sql, self.world_pack_reader_for(world), context, bindings)

    def race_service(self) -> RaceService:
        if self._race_service is None:
            self._race_service = RaceService(
                repo=self.race_repository(),
                world_repository=self.world_repository(),
            )
        return self._race_service

    def perk_service(self) -> WorldPerkService:
        if self._perk_service is None:
            self._perk_service = WorldPerkService(
                repo=self.perk_repository(),
                world_repository=self.world_repository(),
            )
        return self._perk_service

    def location_service(self) -> NamedLocationService:
        if self._location_service is None:
            self._location_service = NamedLocationService(
                repo=self.location_repository(),
                world_repo=self.world_repository(),
            )
        return self._location_service

    def patch_store_service(self) -> PatchStoreService:
        if self._patch_store_service is None:
            self._patch_store_service = PatchStoreService(self.map_cell_repository())
        return self._patch_store_service

    def map_cell_service(self) -> MapCellService:
        if self._map_cell_service is None:
            self._map_cell_service = MapCellService(
                repo=self.map_cell_repository(),
                read_service_factory=self.map_cell_read_service,
            )
        return self._map_cell_service

    def bootstrap_map_cell_writer(self) -> BootstrapMapCellWriter:
        if self._bootstrap_map_cell_writer is None:
            self._bootstrap_map_cell_writer = BootstrapMapCellWriter(
                db=self._db,
                repo=self.map_cell_repository(),
            )
        return self._bootstrap_map_cell_writer

    def terrain_batch_orchestrator(self) -> TerrainBatchOrchestrator:
        if self._terrain_batch_orchestrator is None:
            self._terrain_batch_orchestrator = TerrainBatchOrchestrator(
                map_cell_service=self.map_cell_service(),
            )
        return self._terrain_batch_orchestrator

    def climate_batch_orchestrator(self) -> ClimateBatchOrchestrator:
        if self._climate_batch_orchestrator is None:
            self._climate_batch_orchestrator = ClimateBatchOrchestrator(
                map_cell_service=self.map_cell_service(),
                world_repo=self.world_repository(),
            )
        return self._climate_batch_orchestrator

    def surface_materialization_orchestrator(self) -> WorldSurfaceMaterializationOrchestrator:
        if self._surface_materialization_orchestrator is None:
            self._surface_materialization_orchestrator = WorldSurfaceMaterializationOrchestrator(
                pack=self.pack_materialization_orchestrator(),
                outdoor=self.settlement_outdoor_orchestrator(),
            )
        return self._surface_materialization_orchestrator

    def connection_persist_service(self) -> ConnectionPersistService:
        if self._connection_persist_service is None:
            self._connection_persist_service = ConnectionPersistService(
                node_repo=self.connection_node_repository(),
                edge_repo=self.connection_edge_repository(),
                edge_cell_repo=self.connection_edge_cell_repository(),
            )
        return self._connection_persist_service

    def settlement_persist_service(self) -> SettlementPersistService:
        if self._settlement_persist_service is None:
            self._settlement_persist_service = SettlementPersistService(
                map_cell_service=self.map_cell_service(),
                location_repo=self.location_repository(),
                connection_persist=self.connection_persist_service(),
                connection_edge_repo=self.connection_edge_repository(),
            )
        return self._settlement_persist_service

    def settlement_outdoor_orchestrator(self) -> SettlementOutdoorOrchestrator:
        if self._settlement_outdoor_orchestrator is None:
            sql_persist = SettlementOutdoorSqlPersist(
                db=self._db,
                location_repo=self.location_repository(),
                level_repo=self.location_level_repository(),
                transition_repo_for=lambda context: SqliteTransitionRepository(self._db, context),
                connection_persist=self.connection_persist_service(),
            )
            self._settlement_outdoor_orchestrator = SettlementOutdoorOrchestrator(
                world_repo=self.world_repository(),
                location_repo=self.location_repository(),
                sql_persist=sql_persist,
                generator=SettlementGeneratorService(),
                writer_for=self.world_pack_writer_for,
                facade_for=self.map_cell_query_facade,
                pack_context_for=lambda uid: self.pack_read_services(uid).context,
                snapshot_loader=self.template_snapshot_loader(),
                node_repo=self.connection_node_repository(),
                edge_repo=self.connection_edge_repository(),
            )
        return self._settlement_outdoor_orchestrator

    def state_service(self) -> StateService:
        if self._state_service is None:
            self._state_service = StateService(repo=self.state_repository())
        return self._state_service

    def seed_service(self) -> SeedService:
        if self._seed_service is None:
            self._seed_service = SeedService(db=self._db)
        return self._seed_service

    def entry_refine_orchestrator(self) -> EntryRefineOrchestrator:
        if self._entry_refine_orchestrator is None:
            terrain = self.terrain_batch_orchestrator()
            self._entry_refine_orchestrator = EntryRefineOrchestrator(
                FineTerrainRefineOrchestrator(
                    terrain,
                    region_state_repo=SqliteRegionStateRepository(self._db),
                    relief_loader=self.template_snapshot_loader(),
                    relief_grade_repo=self.relief_grade_repository(),
                ),
                job_repo=self.chunk_refine_job_repository(),
                bake_defaults=PackBakeDefaults.canonical_defaults(),
            )
        return self._entry_refine_orchestrator

    def pack_materialization_orchestrator(self) -> PackMaterializationOrchestrator:
        if self._pack_materialization_orchestrator is None:
            entry = self.entry_refine_orchestrator()
            self._pack_materialization_orchestrator = PackMaterializationOrchestrator(
                self.terrain_batch_orchestrator(),
                region_state_repo=SqliteRegionStateRepository(self._db),
                entry=entry,
                climate_bake=entry.climate_bake,
                job_repo=self.chunk_refine_job_repository(),
                world_repository=self.world_repository(),
                db=self._db,
                read_context_for=lambda uid: self.pack_read_services(uid).context,
                relief_loader=self.template_snapshot_loader(),
                relief_grade_repo=self.relief_grade_repository(),
            )
        return self._pack_materialization_orchestrator
