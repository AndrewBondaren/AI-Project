"""Validate each cold or cached read while the manifest pin is held."""
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from app.application.artifacts.contracts.blobRead import ReadableBlobBackend
from app.application.worldData.pack.encoding.manifestCacheKey import manifest_cache_key
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.worldPack.meta.worldPackManifest import SPATIAL_PACK_WIRE_VERSION
from app.dataModel.worldPack.read.pinnedManifest import (
    ManifestAddress, ManifestCachedRead, ManifestPinRead, ManifestReadReason, ManifestReadRefusal,
    ManifestStorageRead, VerifiedManifestBytes,
)
from app.encoding.canonicalCodec import content_digest


class ManifestGuard(Protocol):
    def manifest_guard(self, request: ManifestPinRead) -> AbstractAsyncContextManager[
        ArtifactRef | ManifestReadRefusal]: ...


class PinnedManifestReader:
    def __init__(self, guard: ManifestGuard, backend: ReadableBlobBackend):
        self._guard = guard
        self._backend = backend

    async def resolve(self, request: ManifestPinRead) -> ManifestAddress | ManifestReadRefusal:
        request = ManifestPinRead.model_validate(request)
        async with self._guard.manifest_guard(request) as ref:
            if isinstance(ref, ManifestReadRefusal):
                return ref
            return ManifestAddress(ref=ref, key=manifest_cache_key(ref))

    async def read_verified(self, request: ManifestStorageRead) -> VerifiedManifestBytes | ManifestReadRefusal:
        request = ManifestStorageRead.model_validate(request)
        async with self._guard.manifest_guard(request.pin) as ref:
            if isinstance(ref, ManifestReadRefusal):
                return ref
            if ref != request.address.ref or manifest_cache_key(ref) != request.address.key:
                return self._refusal(request, ref, ManifestReadReason.IDENTITY_MISMATCH)
            payload = await self._backend.read_verified(ref, max_bytes=request.pin.max_bytes)
            return self._admit(request, ref, payload)

    async def admit_cached(self, request: ManifestCachedRead) -> VerifiedManifestBytes | ManifestReadRefusal:
        request = ManifestCachedRead.model_validate(request)
        async with self._guard.manifest_guard(request.pin) as ref:
            if isinstance(ref, ManifestReadRefusal):
                return ref
            if (ref != request.address.ref or manifest_cache_key(ref) != request.address.key
                    or request.entry.key != request.address.key):
                return self._refusal(request, ref, ManifestReadReason.IDENTITY_MISMATCH)
            payload = request.entry.value
            if len(payload) != ref.nbytes or content_digest(payload).hex() != ref.content_hash:
                return self._refusal(request, ref, ManifestReadReason.INVALID_MANIFEST)
            return self._admit(request, ref, payload)

    @staticmethod
    def _refusal(request: ManifestStorageRead, ref: ArtifactRef, reason: ManifestReadReason) -> ManifestReadRefusal:
        return ManifestReadRefusal(pin_id=request.pin.pin_id, ref=ref, reason=reason)

    def _admit(self, request: ManifestStorageRead, ref: ArtifactRef,
               payload: bytes) -> VerifiedManifestBytes | ManifestReadRefusal:
        try:
            manifest = decode_manifest(payload)
        except ValueError:
            return self._refusal(request, ref, ManifestReadReason.INVALID_MANIFEST)
        if (manifest.world_uid != request.pin.world_uid or manifest.pack_version != SPATIAL_PACK_WIRE_VERSION
                or manifest.content_hash is not None):
            return self._refusal(request, ref, ManifestReadReason.INVALID_MANIFEST)
        return VerifiedManifestBytes(ref=ref, payload=payload)
