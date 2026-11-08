"""Pack-side execution lifetime. Every physical read holds the publication writer until drain."""
from dataclasses import dataclass
from functools import partial
from uuid import UUID

from app.application.artifacts.contracts.blobRead import ReadableBlobBackend
from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.worldData.generators.hydrology.encoding.packCodec import decode_root
from app.application.engine.contracts.invocation.executionStore import ExecutionStore
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest
from app.application.worldData.pack.spatial.openWaterBlobReader import OpenWaterBlobReader
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, PinHolder
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.engine.dag.identity import ExecutionId
from app.dataModel.engine.dag.invocations.record import ExecutionStopIntent
from app.dataModel.worldPack.meta.worldPackManifest import SPATIAL_PACK_WIRE_VERSION
from app.db.repositories.sqlite.artifacts.holderStore import SqliteArtifactHolders
from app.db.repositories.sqlite.snapshotCore.publications.worldPublicationStore import SqliteWorldPublicationStore
from app.db.models.artifacts.catalogRows import ArtifactCatalogRow
from app.ids.deterministicIds import runtime_uid


class PackIdentityConflict(ValueError):
    pass


class PackClosed(PackIdentityConflict):
    pass


class PackIntentUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class CloseReceipt:
    store_id: UUID
    execution_id: ExecutionId
    stop_revision: int


@dataclass(frozen=True)
class PinIntent:
    store_id: UUID
    execution_id: ExecutionId
    invocation_id: str
    logical_read_key: str
    pin_id: str
    world_uid: str


class ExecutionPins:
    @classmethod
    async def bind(cls, store: ExecutionStore, publications: SqliteWorldPublicationStore,
                   holders: SqliteArtifactHolders, registry: ArtifactFormatRegistryBinding,
                   manifest_contract: ArtifactFormatContract[bytes], manifest_version: int, manifest_budget: int):
        """Bind trusted store and registered manifest format once at composition."""
        instance = cls()
        instance._store = store
        instance._id = await store.get_store_id()
        instance._publications = publications
        instance._catalog = holders._catalog
        instance._holders = holders
        instance._scopes = holders._scopes
        instance._access = holders._access
        instance._backend = registry.resolve(manifest_contract)
        instance._contract = manifest_contract
        instance._version = manifest_version
        instance._budget = manifest_budget
        if (not isinstance(instance._backend, ReadableBlobBackend) or manifest_version not in manifest_contract.supported_versions
                or type(manifest_budget) is not int or manifest_budget <= 0):
            raise ValueError("invalid registered manifest reader or budget")
        instance._reader = OpenWaterBlobReader(registry, instance._catalog, holders)
        return instance

    def _owner(self, identity):
        if identity.store_id != self._id:
            raise PackIdentityConflict("foreign DAG store")
        return str(self._id), identity.execution_id

    async def _closed(self, scope, owner):
        return await self._access.one(scope, """SELECT stop_revision FROM pack_execution_closed
            WHERE store_id=? AND execution_id=?""", owner)

    async def _checkpoint(self, execution_id):
        try:
            return await self._store.load(execution_id)
        except KeyError as exc:
            raise PackIdentityConflict("unknown execution") from exc
        except Exception as exc:
            raise PackIntentUnavailable("cannot load trusted execution") from exc

    async def close(self, command: ExecutionStopIntent) -> CloseReceipt:
        if type(command) is not ExecutionStopIntent or type(command.stop_revision) is not int or command.stop_revision <= 0:
            raise PackIdentityConflict("invalid stop command")
        owner = self._owner(command)

        def replay(row):
            if row["stop_revision"] != command.stop_revision:
                raise PackIdentityConflict("conflicting stop revision")
            return CloseReceipt(command.store_id, command.execution_id, row["stop_revision"])

        async with self._scopes.read_scope() as scope:
            existing = await self._closed(scope, owner)
        if existing is None:
            checkpoint = await self._checkpoint(command.execution_id)
            if checkpoint.stop_intent != command or checkpoint.revision != command.stop_revision:
                raise PackIdentityConflict("stop command differs from committed intent")
        async with self._scopes.commits.transaction(runtime_uid()) as scope:
            existing = await self._closed(scope, owner)
            if existing:
                return replay(existing)
            inserted = await self._access.one(scope, """INSERT INTO pack_execution_closed VALUES (?,?,?)
                RETURNING stop_revision""", (*owner, command.stop_revision))
        return replay(inserted)

    async def _binding(self, scope, intent: PinIntent):
        owner = self._owner(intent)
        if await self._closed(scope, owner):
            raise PackClosed("execution is closed")
        rows = await self._access.all(scope, """SELECT * FROM pack_execution_pins WHERE pin_id=?
            OR (store_id=? AND execution_id=? AND invocation_id=? AND logical_read_key=?)""",
            (intent.pin_id, *owner, intent.invocation_id, intent.logical_read_key))
        if rows and (len(rows) != 1 or any(rows[0][k] != v for k, v in (
                ("store_id", owner[0]), ("execution_id", owner[1]), ("invocation_id", intent.invocation_id),
                ("logical_read_key", intent.logical_read_key), ("world_uid", intent.world_uid),
                ("pin_id", intent.pin_id), ("state", "OPEN")))):
            raise PackIdentityConflict("pin identity mismatch")
        return rows[0] if rows else None

    async def acquire(self, intent: PinIntent) -> ArtifactRef:
        owner = self._owner(intent)
        async with self._scopes.commits.transaction(runtime_uid()) as scope, self._scopes.bind(scope):
            row = await self._binding(scope, intent)
            holder = PinHolder(pin_id=intent.pin_id)
            if row:
                ref = await self._catalog._by_id(scope, row["manifest_artifact_id"])
                if not await self._holders.is_held(ref, holder):
                    raise PackIdentityConflict("missing manifest hold")
                return ref
            await self._checkpoint(intent.execution_id)
            publication = await self._publications.read(intent.world_uid, scope=scope.read_scope)
            descriptor = await self._access.one_row(scope, ArtifactCatalogRow, """SELECT * FROM artifact_catalog
                WHERE kind=? AND format_key=? AND format_version=? AND content_hash=?""",
                (self._contract.kind.value, self._contract.key, self._version, publication.pack_hash))
            if descriptor is None:
                raise PackIdentityConflict("missing published manifest")
            ref = self._catalog._descriptor(descriptor)
            if not await self._catalog.is_sealed(ref) or not await self._holders.holders(ref):
                raise PackIdentityConflict("unheld or unsealed published manifest")
            manifest = decode_manifest(await self._backend.read_verified(ref, max_bytes=self._budget))
            if (manifest.world_uid != intent.world_uid or manifest.pack_version != SPATIAL_PACK_WIRE_VERSION
                    or manifest.content_hash is not None):
                raise PackIdentityConflict("foreign or invalid manifest")
            await self._access.one(scope, """INSERT INTO pack_execution_pins
                (pin_id, store_id, execution_id, invocation_id, logical_read_key, world_uid,
                 publication_id, manifest_artifact_id) VALUES (?,?,?,?,?,?,?,?) RETURNING pin_id""",
                (intent.pin_id, *owner, intent.invocation_id, intent.logical_read_key, intent.world_uid,
                 publication.publication_id, descriptor.artifact_id))
            await self._holders.acquire(ref, holder)
            return ref

    async def _pinned_manifest(self, intent):
        async with self._scopes.read_scope() as scope:
            row = await self._binding(scope, intent)
            if row is None:
                raise PackIdentityConflict("unknown pin")
            ref = await self._catalog._by_id(scope, row["manifest_artifact_id"])
            if not await self._holders.is_held(ref, PinHolder(pin_id=intent.pin_id)):
                raise PackIdentityConflict("missing manifest hold")
            return ref

    async def _roots(self, intent):
        async with self._scopes.commits.transaction(runtime_uid()) as scope, self._scopes.bind(scope):
            ref = await self._pinned_manifest(intent)
            if not await self._catalog.is_sealed(ref):
                raise PackIdentityConflict("unsealed manifest")
            manifest = decode_manifest(await self._backend.read_verified(ref, max_bytes=self._budget))
            return tuple(entry.root for entry in manifest.spatial_roots)

    async def _child_owner(self, intent):
        # Called inside the reader's physical-open guard, including after resolving closure.
        return ArtifactRetentionHolder(artifact=await self._pinned_manifest(intent))

    async def read_root(self, intent: PinIntent, ref: ArtifactRef, *, max_bytes: int | None = None) -> bytes:
        if ref not in await self._roots(intent):
            raise PackIdentityConflict("root outside pinned manifest")
        return await self._reader.read_bound_root(ref, partial(self._child_owner, intent), max_bytes=max_bytes)

    async def read_shard(self, intent: PinIntent, ref: ArtifactRef, *, max_bytes: int | None = None) -> bytes:
        owner = partial(self._child_owner, intent)
        for root in await self._roots(intent):
            payload = await self._reader.read_bound_root(root, owner)
            if any(entry.artifact == ref for entry in decode_root(payload, root.format_version).shards):
                return await self._reader.read_bound_shard(ref, owner, max_bytes=max_bytes)
        raise PackIdentityConflict("shard outside pinned manifest")
