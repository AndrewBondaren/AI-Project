"""World-map pack wiring: paths/io factories and read facades."""

from threading import RLock
from pathlib import Path

from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.storage.artifactLeases import IArtifactLeases
from app.application.worldData.pack.encoding.climateFieldFormat import CLIMATE_FIELD_FORMAT
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend
from app.storage.artifacts.manifestBlobBackend import ManifestBlobBackend

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.contracts.manifestBytesCodec import ManifestBytesCodec
from app.application.cache.service.cacheBindingRegistry import CacheBindingRegistry
from app.application.cache.service.cacheService import CacheService

from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.parentLightCache import ParentLightCache
from app.application.worldData.pack.read.packReadServices import PackReadServices, build_pack_read_services
from app.application.worldData.mapCells.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.mapCells.mapCellReadService import MapCellReadService
from app.db.models.world import World
from app.dataModel.worldPack.meta.manifestCacheContract import MANIFEST_BYTES_CONTRACT
from app.core.appSettings import app_settings
from app.db.repositories.sqlite.regionStateRepository import SqliteRegionStateRepository
from app.db.repositories.sqlite.artifacts.access.artifactScope import SqliteArtifactScope
from app.db.repositories.sqlite.artifacts.leaseStore import SqliteArtifactLeases
from app.db.repositories.sqlite.artifacts.operationArtifacts import SqliteOperationArtifacts
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.capabilities.scopeRegistry import SqliteScopeRegistry
from app.db.repositories.sqlite.shared.transactions.transactionDriver import SqliteTransactionDriver
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.db.repositories.sqlite.snapshotCore.operations.operationStore import SqliteOperationStore
from app.db.repositories.sqlite.snapshotCore.operations.publicationEvidence import SqlitePublicationEvidence
from app.db.repositories.sqlite.snapshotCore.operations.terminalCodec import StoredTerminalCodec
from app.db.repositories.sqlite.snapshotCore.publications.playerPublicationStore import SqlitePlayerPublicationStore
from app.db.repositories.sqlite.snapshotCore.publications.worldPublicationStore import SqliteWorldPublicationStore


class PacksWiring:
    """Per-world pack I/O and read-service factories (``world_uid`` scoped)."""

    @staticmethod
    def register_manifest_format(registry: ArtifactFormatRegistryBinding, artifact_root: Path,
                                 leases: IArtifactLeases, *, max_bytes: int) -> ManifestBlobBackend:
        backend = ManifestBlobBackend(artifact_root, leases, max_bytes=max_bytes)
        registry.register(backend.contract, backend)
        return backend

    @staticmethod
    def register_climate_field_format(registry: ArtifactFormatRegistryBinding, artifact_root: Path,
                                      leases: IArtifactLeases) -> None:
        registry.register(CLIMATE_FIELD_FORMAT, ContentAddressedBlobBackend(artifact_root, CLIMATE_FIELD_FORMAT, leases))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pack_read_services: dict[str, PackReadServices] = {}
        self._parent_light_caches: dict[str, ParentLightCache] = {}
        self._manifest_cache_service: CacheService | None = None
        self._manifest_cache_lock = RLock()
        self._pack_formats: ArtifactFormatRegistryBinding | None = None

    def initialize_pack_storage(self) -> None:
        settings = app_settings.world_pack
        if settings is None or settings.manifest_max_bytes is None:
            return
        with self._manifest_cache_lock:
            if self._pack_formats is not None:
                return
            scopes = SqliteScopeRegistry(self._db)
            access = ScopedSqliteAccess(scopes)
            commits = SqlitePublicationCommitStore(self._db, scopes, SqliteTransactionDriver())
            artifacts = SqliteOperationArtifacts(access)
            evidence = SqlitePublicationEvidence(commits, SqliteWorldPublicationStore(commits, access),
                                                 SqlitePlayerPublicationStore(commits, access), access)
            operations = SqliteOperationStore(commits, access, StoredTerminalCodec(), evidence, artifacts)
            leases = SqliteArtifactLeases(SqliteArtifactScope(commits, access), operations, artifacts)
            registry = ArtifactFormatRegistryBinding()
            root = Path(self._db.path).resolve().parent / "artifacts"
            self.register_manifest_format(registry, root, leases, max_bytes=settings.manifest_max_bytes)
            self.register_climate_field_format(registry, root, leases)
            self._pack_formats = registry

    def pack_manifest_cache_service(self) -> CacheService:
        with self._manifest_cache_lock:
            if self._manifest_cache_service is None:
                settings = app_settings.world_pack
                if settings is None:
                    raise ValueError("World Pack V2 requires explicit [world_pack.manifest_cache] configuration")
                binding = CacheBinding(MANIFEST_BYTES_CONTRACT, ManifestBytesCodec())
                self._manifest_cache_service = CacheService(
                    MemoryCache(settings.manifest_cache), CacheBindingRegistry((binding,)))
            return self._manifest_cache_service

    def pack_read_services(self, world_uid: str) -> PackReadServices:
        services = self._pack_read_services.get(world_uid)
        if services is None:
            services = build_pack_read_services(
                world_uid,
                self.patch_store_service(),
                db_path=app_settings.db_path,
                planning=self.surface_planning(), capture=self.surface_planning_capture(),
                region_state_repo=SqliteRegionStateRepository(self._db),
            )
            self._pack_read_services[world_uid] = services
        return services

    def map_cell_read_service(self, world_uid: str) -> MapCellReadService:
        return MapCellReadService(self.pack_read_services(world_uid))

    def map_cell_query_facade(self, world_uid: str) -> MapCellQueryFacade:
        return self.pack_read_services(world_uid).gameplay

    def pack_debug_read_facade(self, world_uid: str):
        return self.pack_read_services(world_uid).debug

    def pack_loading_progress_facade(self, world_uid: str):
        return self.pack_read_services(world_uid).loading

    def world_pack_paths_for(self, world: World) -> WorldPackPaths:
        return WorldPackPaths.for_world(world, app_settings.db_path)

    # LEGACY REMOVE(SP-P-V1-REMOVE/V1-03) Replace V1 writer construction at cutover.
    def world_pack_writer_for(self, world: World) -> WorldPackWriter:
        """Writer with process-scoped parent-light cache (shared across HTTP calls)."""
        return WorldPackWriter(
            self.world_pack_paths_for(world),
            parent_light_cache=self.parent_light_cache_for(world.world_uid),
        )

    def parent_light_cache_for(self, world_uid: str) -> ParentLightCache:
        """Process-local cache keyed by world — latency only; disk remains SoT."""
        cache = self._parent_light_caches.get(world_uid)
        if cache is None:
            cache = ParentLightCache()
            self._parent_light_caches[world_uid] = cache
        return cache

    def world_pack_reader_for(self, world: World) -> WorldPackReader:
        return WorldPackReader(self.world_pack_paths_for(world))

    def world_pack_paths(self, world_uid: str) -> WorldPackPaths:
        return WorldPackPaths.from_db_parent(app_settings.db_path, world_uid)

    # LEGACY REMOVE(SP-P-V1-REMOVE/V1-03) Replace V1 writer construction at cutover.
    def world_pack_writer(self, world_uid: str) -> WorldPackWriter:
        return WorldPackWriter(
            self.world_pack_paths(world_uid),
            parent_light_cache=self.parent_light_cache_for(world_uid),
        )

    def world_pack_reader(self, world_uid: str) -> WorldPackReader:
        return WorldPackReader(self.world_pack_paths(world_uid))
