"""Read open-water members reachable from a live execution pin."""
from functools import partial

from app.application.artifacts.contracts.blobRead import ReadableBlobBackend
from app.application.worldData.generators.hydrology.encoding.packCodec import decode_root
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest
from app.application.worldData.pack.spatial.openWaterBlobReader import OpenWaterBlobReader
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder
from app.dataModel.artifacts.references import ArtifactRef
from app.db.repositories.sqlite.worldPack.executionPins import ExecutionPins, PinIntent, PackIdentityConflict


class PinnedSpatialReader:
    def __init__(self, pins: ExecutionPins, backend: ReadableBlobBackend, manifest_budget: int,
                 reader: OpenWaterBlobReader):
        self._pins = pins
        self._backend = backend
        self._budget = manifest_budget
        self._reader = reader

    async def _roots(self, intent):
        async with self._pins.hold_open(intent) as ref:
            manifest = decode_manifest(await self._backend.read_verified(ref, max_bytes=self._budget))
            return tuple(entry.root for entry in manifest.spatial_roots)

    async def _child_owner(self, intent):
        # Called inside the reader's physical-open guard, including after resolving closure.
        return ArtifactRetentionHolder(artifact=await self._pins.held_manifest(intent))

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
