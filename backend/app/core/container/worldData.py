"""worldData wiring: domain services, persist, transitions, orchestrators."""

from collections.abc import Mapping, Sequence
from threading import RLock

from app.application.worldData.planning.composition.planProviders import WorldPlanProviders, register_world_plan_providers
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler
from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
from app.application.worldData.planning.guards.sourcePublication import SourcePublicationGuard

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.service.cacheService import CacheService
from app.application.planning.providers.planRegistry import PlanRegistry
from app.application.planning.service.planningService import PlanningService
from app.core.appSettings import app_settings
from app.dataModel.planning.policy.planningRuntimeSettings import PlanningRuntimeSettings

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
from app.application.worldData.materialize.terrain.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.materialize.climate.climateBatchOrchestrator import ClimateBatchOrchestrator
from app.application.worldData.materialize.surface.worldSurfaceMaterializationOrchestrator import (
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
from app.application.worldData.pack.bake.l0.packMaterializationOrchestrator import PackMaterializationOrchestrator
from app.application.worldData.pack.bake.detailed.packDetailedBakeOrchestrator import PackDetailedBakeOrchestrator
from app.application.worldData.pack.bake.finalize.packBakePublisher import PackBakePublisher
from app.application.worldData.pack.refine.entry.entryRefineOrchestrator import EntryRefineOrchestrator
from app.application.worldData.pack.refine.fine.chunk.fineChunkRunner import FineChunkRunner
from app.application.worldData.pack.refine.fine.fineScenePathRefine import FineScenePathRefine
from app.application.worldData.pack.refine.fine.fineRectDrain import FineRectDrain
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
        self._pack_bake_publisher: PackBakePublisher | None = None
        self._entry_refine_orchestrator = None
        self._planning_resources: PlanningRuntimeSettings | None = None
        self._planning_memory_cache: MemoryCache | None = None
        self._planning_cache_service: CacheService | None = None
        self._planning_cache_lock = RLock()
        self._plan_registry: PlanRegistry | None = None
        self._planning_service: PlanningService | None = None
        self._world_plan_providers: WorldPlanProviders | None = None
        self._surface_planning: SurfacePlanningAssembler | None = None
        self._surface_capture: SurfacePlanningCapture | None = None
        self._source_publication: SourcePublicationGuard | None = None

    def planning_resources(self) -> PlanningRuntimeSettings:
        with self._planning_cache_lock:
            if self._planning_resources is None:
                if app_settings.planning is None:
                    raise ValueError("Planning requires explicit [planning.cache] and [planning.execution] configuration")
                self._planning_resources = PlanningRuntimeSettings.model_validate(app_settings.planning)
            return self._planning_resources

    def planning_memory_cache(self) -> MemoryCache:
        with self._planning_cache_lock:
            if self._planning_memory_cache is None:
                self._planning_memory_cache = MemoryCache(self.planning_resources().cache)
            return self._planning_memory_cache

    def planning_cache_service(self) -> CacheService:
        with self._planning_cache_lock:
            if self._planning_cache_service is None:
                self._planning_cache_service = CacheService(self.planning_memory_cache(), self.planning_resources().cache)
            return self._planning_cache_service

    def plan_registry(self) -> PlanRegistry:
        with self._planning_cache_lock:
            if self._plan_registry is None:
                self._plan_registry = PlanRegistry()
            return self._plan_registry

    def planning_service(self) -> PlanningService:
        with self._planning_cache_lock:
            if self._planning_service is None:
                self._planning_service = PlanningService(self.plan_registry(),
                    self.planning_cache_service(), self.planning_resources().execution)
            return self._planning_service

    def surface_planning(self) -> SurfacePlanningAssembler:
        with self._planning_cache_lock:
            if self._surface_planning is None:
                if self._world_plan_providers is None:
                    self._world_plan_providers = register_world_plan_providers(self.plan_registry())
                self._surface_planning = SurfacePlanningAssembler(self.planning_service(),
                    self.plan_registry(), self._world_plan_providers)
            return self._surface_planning

    def surface_planning_capture(self) -> SurfacePlanningCapture:
        with self._planning_cache_lock:
            if self._surface_capture is None:
                self._surface_capture = SurfacePlanningCapture()
            return self._surface_capture

    def surface_planning_entry(self) -> SurfacePlanningEntry:
        return SurfacePlanningEntry(self.surface_planning(), self.surface_planning_capture())

    def region_state_repository(self) -> SqliteRegionStateRepository:
        return SqliteRegionStateRepository(self._db)

    def source_publication_guard(self) -> SourcePublicationGuard:
        with self._planning_cache_lock:
            if self._source_publication is None:
                self._source_publication = SourcePublicationGuard(self.world_repository(),
                    self.location_repository(), self.surface_planning_capture())
            return self._source_publication

    def shutdown_planning(self, *, wait: bool = True) -> None:
        if self._planning_service is not None:
            self._planning_service.shutdown(wait=wait)

    def world_service(self) -> WorldService:
        if self._world_service is None:
            from app.application.worldData.regions.declaredRegionEdit import DeclaredRegionEditor
            self._world_service = WorldService(repo=self.world_repository(),
                region_editor=DeclaredRegionEditor(self._db, SqliteRegionStateRepository(self._db)))
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
            self._terrain_batch_orchestrator = TerrainBatchOrchestrator()
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
                detailed=PackDetailedBakeOrchestrator(
                    self.terrain_batch_orchestrator(),
                    relief_loader=self.template_snapshot_loader(),
                    relief_grade_repo=self.relief_grade_repository(),
                ),
                relief_loader=self.template_snapshot_loader(),
                planning=self.surface_planning(), capture=self.surface_planning_capture(),
                db=self._db, publication_guard=self.source_publication_guard(),
                region_state_repo=self.region_state_repository(),
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
            runner = FineChunkRunner(terrain)
            self._entry_refine_orchestrator = EntryRefineOrchestrator(
                FineScenePathRefine(
                    terrain,
                    runner=runner,
                    relief_grade_repo=self.relief_grade_repository(),
                ),
                FineRectDrain(
                    terrain,
                    runner=runner,
                    relief_loader=self.template_snapshot_loader(),
                    relief_grade_repo=self.relief_grade_repository(),
                ),
                job_repo=self.chunk_refine_job_repository(),
                bake_defaults=PackBakeDefaults.canonical_defaults(),
            )
        return self._entry_refine_orchestrator

    def pack_bake_publisher(self) -> PackBakePublisher:
        if self._pack_bake_publisher is None:
            self._pack_bake_publisher = PackBakePublisher(
                db=self._db,
                world_repository=self.world_repository(),
                publication_guard=self.source_publication_guard(),
                read_context_for=lambda uid: self.pack_read_services(uid).context,
            )
        return self._pack_bake_publisher

    def pack_materialization_orchestrator(self) -> PackMaterializationOrchestrator:
        if self._pack_materialization_orchestrator is None:
            entry = self.entry_refine_orchestrator()
            self._pack_materialization_orchestrator = PackMaterializationOrchestrator(
                planning=self.surface_planning(), capture=self.surface_planning_capture(),
                publisher=self.pack_bake_publisher(),
                region_state_repo=self.region_state_repository(),
                entry=entry,
                climate_bake=entry.climate_bake,
                relief_loader=self.template_snapshot_loader(),
                relief_grade_repo=self.relief_grade_repository(),
            )
        return self._pack_materialization_orchestrator
