"""Fenced reserve, write, verification and seal for one bound format."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from pydantic import BaseModel

from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.artifacts.errors import ArtifactStorageInvariantError
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.storage.artifactCatalog import IArtifactCatalog
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.events import ArtifactLogActivity, ArtifactLogRecord
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.staging.preparedArtifact import PreparedArtifact


class IArtifactWriteAdmission(Protocol):
    def require_standalone(self) -> None: ...
    async def assert_writable(self, lease: OperationLeaseRef) -> None: ...
    def writer(self, reservation: StagingReservation) -> AbstractAsyncContextManager[None]: ...


class ArtifactStageWriter[C: bytes | BaseModel]:
    def __init__(self, contract: ArtifactFormatContract[C], registry: ArtifactFormatRegistryBinding,
                 catalog: IArtifactCatalog, admission: IArtifactWriteAdmission,
                 log: ArtifactLifecycleLog) -> None:
        backend = registry.resolve(contract)
        if backend.write_admission is not admission:
            raise PublicationInfrastructureError("backend uses another write admission")
        catalog.assert_write_admission(admission)
        self._contract, self._registry, self._backend = contract, registry, backend
        self._catalog, self._admission, self._log = catalog, admission, log

    async def write(self, lease: OperationLeaseRef, prepared: PreparedArtifact[C]) -> ArtifactRef:
        self._admission.require_standalone()
        if self._backend.write_admission is not self._admission:
            raise ArtifactStorageInvariantError("backend write admission changed")
        ref = prepared.descriptor
        try:
            self._registry.validate(ref)
        except (ValueError, TypeError) as error:
            raise ArtifactStorageInvariantError("prepared descriptor lost registered binding") from error
        await self._admission.assert_writable(lease)
        reservation = await self._catalog.reserve(lease, ref)
        if reservation.lease != lease or reservation.ref != ref:
            raise ArtifactStorageInvariantError("catalog reservation differs from requested binding")
        await self._backend.write(reservation, prepared.content)
        async with self._admission.writer(reservation):
            await self._admission.assert_writable(lease)
            await self._registry.verify(ref)
            await self._admission.assert_writable(lease)
            sealed = await self._catalog.seal(reservation)
            if sealed != ref:
                raise ArtifactStorageInvariantError("catalog seal differs from reservation")
        self._log.emit(ArtifactLogRecord(activity=ArtifactLogActivity.ARTIFACT_SEALED,
            operation_id=lease.operation_id, world_uid=lease.world_uid,
            preparation_fingerprint=lease.preparation_fingerprint, request_fingerprint=None,
            artifact_hash=ref.content_hash))
        return ref
