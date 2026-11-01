"""Stage already prepared content through registered typed backends."""

from pydantic import BaseModel, TypeAdapter
from app.application.encoding.canonicalCodec import content_digest
from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.artifacts.contracts.stagingPort import IArtifactStaging
from app.application.artifacts.contracts.holderPort import IArtifactHolders
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.storage.artifactCatalog import IArtifactCatalog
from app.application.artifacts.storage.artifactLeases import IArtifactLeases
from app.application.artifacts.lifecycle.artifactGc import ArtifactGarbageCollector
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.application.publication.service.operationLedger import OperationLedger
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.holders import ArtifactHolderRef, VerifiedArtifactRef
from app.dataModel.artifacts.lifecycle.gc import GcReport
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord
from app.dataModel.artifacts.events import ArtifactLogRecord, ArtifactLogActivity
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.values import FormatVersion
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class ArtifactStagingService:
    def __init__(self, registry: ArtifactFormatRegistryBinding, catalog: IArtifactCatalog,
                 leases: IArtifactLeases, holders: IArtifactHolders, gc: ArtifactGarbageCollector,
                 ledger: OperationLedger, log: ArtifactLifecycleLog) -> None:
        self._registry, self._catalog, self._leases = registry, catalog, leases
        self._holders, self._gc, self._ledger, self._log = holders, gc, ledger, log

    async def open_operation(self, operation_id: EntityUid, world_uid: EntityUid, kind: OperationKind,
                             preparation_fingerprint: RevisionHex) -> OperationLeaseRef:
        return await self._leases.open_operation(operation_id, world_uid, kind, preparation_fingerprint)

    async def reserve(self, lease: OperationLeaseRef, descriptor: ArtifactRef) -> StagingReservation:
        lease = OperationLeaseRef.model_validate(lease, strict=True)
        descriptor = ArtifactRef.model_validate(descriptor, strict=True)
        self._registry.validate(descriptor)
        await self._leases.assert_writable(lease)
        reservation = StagingReservation.model_validate(await self._catalog.reserve(lease, descriptor), strict=True)
        if reservation.lease != lease or reservation.ref != descriptor:
            raise PublicationInfrastructureError("catalog reservation differs from requested binding")
        return reservation

    async def seal(self, reservation: StagingReservation) -> ArtifactRef:
        reservation = StagingReservation.model_validate(reservation, strict=True)
        # Backend write claim has ended; acquire one short claim for verification/seal.
        async with self._leases.writer(reservation):
            await self._leases.assert_writable(reservation.lease)
            await self._registry.verify(reservation.ref)
            await self._leases.assert_writable(reservation.lease)
            ref = await self._catalog.seal(reservation)
            if ref != reservation.ref:
                raise PublicationInfrastructureError("catalog seal differs from reservation")
        self._log.emit(ArtifactLogRecord(activity=ArtifactLogActivity.ARTIFACT_SEALED,
            operation_id=reservation.lease.operation_id, world_uid=reservation.lease.world_uid,
            preparation_fingerprint=reservation.lease.preparation_fingerprint, request_fingerprint=None,
            artifact_hash=ref.content_hash))
        return ref

    async def finish_preparation(self, lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]) -> OperationRecord:
        lease = OperationLeaseRef.model_validate(lease, strict=True)
        refs = TypeAdapter(tuple[ArtifactRef, ...]).validate_python(refs, strict=True)
        return await self._leases.finish_preparation(lease, refs)

    async def verify(self, ref: ArtifactRef, holder: ArtifactHolderRef) -> VerifiedArtifactRef:
        ref = ArtifactRef.model_validate(ref, strict=True)
        holder = TypeAdapter(ArtifactHolderRef).validate_python(holder, strict=True)
        async with self._catalog.guard(ref):
            if not await self._catalog.is_sealed(ref) or not await self._holders.is_held(ref, holder):
                raise ValueError("artifact must be sealed and held by the exact holder")
            await self._registry.verify(ref)
        return VerifiedArtifactRef(ref=ref, holder=holder)

    async def recover(self, operation_id: EntityUid) -> OperationRecord:
        return await self._ledger.recover(operation_id)

    async def cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord:
        return await self._ledger.cancel(operation_id, fence)

    async def collect(self, operation_id: EntityUid, candidates: tuple[ArtifactRef, ...]) -> GcReport:
        return await self._gc.collect(operation_id, candidates)


class TypedArtifactStager[C: bytes | BaseModel]:
    def __init__(self, contract: ArtifactFormatContract[C], format_version: FormatVersion,
                 registry: ArtifactFormatRegistryBinding, staging: IArtifactStaging) -> None:
        registry.resolve(contract)
        format_version = TypeAdapter(FormatVersion).validate_python(format_version, strict=True)
        if format_version not in contract.supported_versions:
            raise ValueError("unsupported artifact version")
        self._contract, self._version, self._registry, self._staging = contract, format_version, registry, staging

    async def stage(self, lease: OperationLeaseRef, content: C) -> ArtifactRef:
        lease = OperationLeaseRef.model_validate(lease, strict=True)
        data = self._registry.encode(self._contract, content)
        # Count belongs to the same domain binding as encode/decode, not a second mechanism.
        rows = None if self._contract.row_count is None else self._contract.row_count(content)
        ref = ArtifactRef(kind=self._contract.kind, format_key=self._contract.key, format_version=self._version,
            content_hash=content_digest(data).hex(), nbytes=len(data), row_count=rows)
        reservation = await self._staging.reserve(lease, ref)
        await self._registry.resolve(self._contract).write(reservation, content)
        return await self._staging.seal(reservation)
