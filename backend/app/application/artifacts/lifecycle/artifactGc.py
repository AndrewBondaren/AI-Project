"""Explicit guarded collection; no TTL, scheduler or release of live holds."""

from pydantic import TypeAdapter
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.storage.artifactCatalog import IArtifactCatalog
from app.application.artifacts.contracts.holderPort import IArtifactHolders
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.gc import GcReport
from app.dataModel.artifacts.events import ArtifactLogRecord, ArtifactLogActivity
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class ArtifactGarbageCollector:
    def __init__(self, registry: ArtifactFormatRegistryBinding, catalog: IArtifactCatalog,
                 holders: IArtifactHolders, log: ArtifactLifecycleLog) -> None:
        self._registry, self._catalog, self._holders, self._log = registry, catalog, holders, log

    async def collect(self, operation_id: EntityUid, candidates: tuple[ArtifactRef, ...]) -> GcReport:
        operation_id = TypeAdapter(EntityUid).validate_python(operation_id, strict=True)
        candidates = TypeAdapter(tuple[ArtifactRef, ...]).validate_python(candidates, strict=True)
        if len(set(candidates)) != len(candidates):
            raise ValueError("duplicate GC candidates")
        deleted: list[ArtifactRef] = []
        retained: list[ArtifactRef] = []
        failed: list[FieldPathError] = []
        for ref in candidates:
            try:
                self._registry.validate(ref)
                async with self._catalog.guard(ref):
                    actual = await self._catalog.read(ref)
                    if actual is None:
                        raise ValueError("unknown artifact catalog identity")
                    if actual != ref:
                        raise PublicationInfrastructureError("catalog identity differs from GC candidate")
                    if await self._holders.holders(ref):
                        retained.append(ref)
                        continue
                    # Storage must exclude surviving claims when there are no holds.
                    await self._registry.delete(ref)
                    await self._catalog.mark_deleted(ref)
                    deleted.append(ref)
                self._emit(operation_id, ref, ArtifactLogActivity.GC_DELETED)
            except (OSError, ValueError) as exc:
                failed.append(FieldPathError(path=(), message=str(exc)))
                self._emit(operation_id, ref, ArtifactLogActivity.GC_FAILED)
        return GcReport(deleted=tuple(deleted), retained=tuple(retained), failed=tuple(failed))

    def _emit(self, operation_id: EntityUid, ref: ArtifactRef, activity: ArtifactLogActivity) -> None:
        self._log.emit(ArtifactLogRecord(activity=activity, operation_id=operation_id, world_uid=None,
            preparation_fingerprint=None, request_fingerprint=None, artifact_hash=ref.content_hash))
