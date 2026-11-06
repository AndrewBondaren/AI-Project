"""Explicit guarded collection; no TTL, scheduler or release of live holds."""

from pydantic import TypeAdapter
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.storage.artifactCatalog import IArtifactCatalog
from app.application.artifacts.contracts.holderPort import IArtifactHolders
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.gc import GcReport, ArtifactGcFailure, GcFailureStage
from app.dataModel.artifacts.events import ArtifactLogRecord, ArtifactLogActivity
from app.dataModel.identity.uid import EntityUid


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
        failed: list[ArtifactGcFailure] = []
        for ref in candidates:
            held = False
            stage = GcFailureStage.VALIDATE
            body_error: OSError | ValueError | None = None
            body_stage = stage
            try:
                self._registry.validate(ref)
                stage = GcFailureStage.GUARD_ENTER
                async with self._catalog.guard(ref):
                    try:
                        stage = GcFailureStage.CATALOG_READ
                        actual = await self._catalog.read(ref)
                        if actual is None:
                            raise ValueError("unknown artifact catalog identity")
                        if actual != ref:
                            raise PublicationInfrastructureError("catalog identity differs from GC candidate")
                        stage = GcFailureStage.HOLDERS_READ
                        held = bool(await self._holders.holders(ref))
                        if not held:
                            stage = GcFailureStage.DELETE
                            await self._registry.delete(ref)
                            stage = GcFailureStage.MARK_DELETED
                            await self._catalog.mark_deleted(ref)
                    except (OSError, ValueError) as exc:
                        body_error, body_stage = exc, stage
                        raise
                    finally:
                        stage = GcFailureStage.GUARD_EXIT
            except (OSError, ValueError) as exc:
                failure = self._log.create_gc_failure(ref=ref,
                    stage=body_stage if exc is body_error else stage, cause=exc)
                failed.append(failure)
                self._log.emit_gc_failure(operation_id=operation_id, failure=failure, cause=exc)
            else:
                if held:
                    retained.append(ref)
                else:
                    deleted.append(ref)
                    self._emit(operation_id, ref, ArtifactLogActivity.GC_DELETED)
        return GcReport(deleted=tuple(deleted), retained=tuple(retained), failed=tuple(failed))

    def _emit(self, operation_id: EntityUid, ref: ArtifactRef, activity: ArtifactLogActivity) -> None:
        self._log.emit(ArtifactLogRecord(activity=activity, operation_id=operation_id, world_uid=None,
            preparation_fingerprint=None, request_fingerprint=None, artifact_hash=ref.content_hash))
