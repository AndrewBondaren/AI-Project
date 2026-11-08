"""Read a single held open-water artifact under the catalog's GC guard."""
from collections.abc import Awaitable, Callable

from pydantic import TypeAdapter

from app.application.artifacts.contracts.blobRead import CorruptBlobError, ReadableBlobBackend
from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.artifacts.contracts.holderPort import IArtifactHolders
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.storage.artifactCatalog import IArtifactCatalog
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldData.generators.hydrology.encoding.packFormats import ROOT_FORMAT, SHARD_FORMAT
from app.dataModel.artifacts.lifecycle.holders import ArtifactHolderRef
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.hydrology.pack.profile import ROOT_V1, SHARD_V1
from app.dataModel.spatial.readFailureReason import SpatialReadFailureReason as Reason


class SpatialBlobReadError(Exception):
    def __init__(self, reason: Reason):
        self.reason = reason
        super().__init__(reason.value)


_HOLDER = TypeAdapter(ArtifactHolderRef)


class OpenWaterBlobReader:
    def __init__(self, registry: ArtifactFormatRegistryBinding, catalog: IArtifactCatalog, holders: IArtifactHolders):
        self._registry = registry
        self._catalog = catalog
        self._holders = holders

    async def read_root(self, ref: ArtifactRef, holder: ArtifactHolderRef, *, max_bytes: int | None = None) -> bytes:
        return await self._read(ref, holder, ROOT_FORMAT, ROOT_V1.max_bytes, max_bytes)

    async def read_shard(self, ref: ArtifactRef, holder: ArtifactHolderRef, *, max_bytes: int | None = None) -> bytes:
        return await self._read(ref, holder, SHARD_FORMAT, SHARD_V1.max_bytes, max_bytes)

    async def read_bound_root(self, ref: ArtifactRef, admission: Callable[[], Awaitable[ArtifactHolderRef]],
                              *, max_bytes: int | None = None) -> bytes:
        return await self._read(ref, None, ROOT_FORMAT, ROOT_V1.max_bytes, max_bytes, admission)

    async def read_bound_shard(self, ref: ArtifactRef, admission: Callable[[], Awaitable[ArtifactHolderRef]],
                               *, max_bytes: int | None = None) -> bytes:
        return await self._read(ref, None, SHARD_FORMAT, SHARD_V1.max_bytes, max_bytes, admission)

    async def _read(self, ref: ArtifactRef, holder: ArtifactHolderRef | None, contract: ArtifactFormatContract[bytes],
                    cap: int, max_bytes: int | None,
                    admission: Callable[[], Awaitable[ArtifactHolderRef]] | None = None) -> bytes:
        if type(ref) is not ArtifactRef or isinstance(holder, dict):
            raise ValueError("expected typed artifact and holder references")
        ref = ArtifactRef.model_validate(ref, strict=True)
        validated = _HOLDER.validate_python(holder, strict=True) if admission is None else None
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
            raise ValueError("invalid read budget")
        if (ref.kind is not contract.kind or ref.format_key != contract.key
                or ref.format_version not in contract.supported_versions):
            raise SpatialBlobReadError(Reason.UNSUPPORTED_FORMAT)
        if not 0 < ref.nbytes <= cap:
            raise SpatialBlobReadError(Reason.SOURCE_CORRUPT)
        budget = cap if max_bytes is None else min(max_bytes, cap)
        if ref.nbytes > budget:
            raise SpatialBlobReadError(Reason.RESOURCE_LIMIT)
        try:
            backend = self._registry.resolve(contract)
        except (TypeError, ValueError) as exc:
            raise SpatialBlobReadError(Reason.SOURCE_UNAVAILABLE) from exc
        if not isinstance(backend, ReadableBlobBackend):
            raise SpatialBlobReadError(Reason.SOURCE_UNAVAILABLE)
        try:
            async with self._catalog.guard(ref):
                holder = await admission() if admission is not None else validated
                if holder is None:
                    raise ValueError("missing artifact holder")
                try:
                    actual = await self._catalog.read(ref)
                except ValueError as exc:
                    raise SpatialBlobReadError(Reason.SOURCE_CORRUPT) from exc
                if actual is None:
                    raise SpatialBlobReadError(Reason.SOURCE_MISSING)
                if actual != ref:
                    raise SpatialBlobReadError(Reason.SOURCE_CORRUPT)
                if not await self._catalog.is_sealed(ref) or not await self._holders.is_held(ref, holder):
                    raise SpatialBlobReadError(Reason.SOURCE_UNAVAILABLE)
                try:
                    return await backend.read_verified(ref, max_bytes=budget)
                except CorruptBlobError as exc:
                    raise SpatialBlobReadError(Reason.SOURCE_CORRUPT) from exc
                except PublicationInfrastructureError as exc:
                    if isinstance(exc.__cause__, FileNotFoundError):
                        raise SpatialBlobReadError(Reason.SOURCE_MISSING) from exc
                    raise
        except (PublicationInfrastructureError, OSError) as exc:
            raise SpatialBlobReadError(Reason.SOURCE_UNAVAILABLE) from exc
