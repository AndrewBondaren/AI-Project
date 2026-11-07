"""Artifact staging/holder/GC events through the project's shared logging facade."""

from app.core.logging.contracts import LogConsumer, UnknownLogConsumerError
from app.core.logging.consumers import get_consumer_logger

from app.core.logLevel import LogLevel, to_logging_level
from app.dataModel.artifacts.events import ArtifactLogActivity, ArtifactLogRecord
from app.dataModel.artifacts.lifecycle.gc import ArtifactGcFailure, GcFailureCode, GcFailureStage
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.ids.deterministicIds import runtime_uid


_LOGGER = get_consumer_logger(LogConsumer.ARTIFACTS)
_LEVELS: dict[ArtifactLogActivity, LogLevel] = {
    ArtifactLogActivity.ARTIFACT_SEALED: LogLevel.DEBUG,
    ArtifactLogActivity.LEASE_RELEASED: LogLevel.INFO,
    ArtifactLogActivity.GC_DELETED: LogLevel.INFO,
    ArtifactLogActivity.GC_FAILED: LogLevel.ERROR,
}


class ArtifactLifecycleLog:
    __slots__ = ()

    @staticmethod
    def create_gc_failure(*, ref: ArtifactRef, stage: GcFailureStage,
                          cause: OSError | ValueError) -> ArtifactGcFailure:
        if not isinstance(cause, (OSError, ValueError)):
            raise TypeError("unsupported GC cause")
        return ArtifactGcFailure(failure_id=runtime_uid(), ref=ref, stage=stage,
            code=GcFailureCode.IO_ERROR if isinstance(cause, OSError) else GcFailureCode.VALUE_ERROR,
            exception_type=type(cause).__module__ + "." + type(cause).__qualname__,
            message=str(cause), errno=cause.errno if isinstance(cause, OSError) else None,
            winerror=getattr(cause, "winerror", None) if isinstance(cause, OSError) else None)

    def emit_gc_failure(self, *, operation_id: EntityUid, failure: ArtifactGcFailure,
                        cause: OSError | ValueError) -> None:
        if type(failure) is not ArtifactGcFailure:
            raise TypeError("expected a typed ArtifactGcFailure")
        failure = ArtifactGcFailure.model_validate(failure, strict=True)
        self.emit(ArtifactLogRecord(activity=ArtifactLogActivity.GC_FAILED,
            operation_id=operation_id, world_uid=None, preparation_fingerprint=None,
            request_fingerprint=None, artifact_hash=failure.ref.content_hash, gc_failure=failure), cause=cause)

    def emit(self, record: ArtifactLogRecord, *, cause: Exception | None = None) -> None:
        """Submit a reported storage fact without executing storage work or adding a world UID."""
        if type(record) is not ArtifactLogRecord:
            raise TypeError("expected a typed ArtifactLogRecord")
        record = ArtifactLogRecord.model_validate(record, strict=True)
        if record.activity is ArtifactLogActivity.GC_FAILED:
            if not isinstance(cause, (OSError, ValueError)):
                raise TypeError("GC_FAILED requires an OS or value error")
            failure = record.gc_failure
            assert failure is not None
            expected = (GcFailureCode.IO_ERROR if isinstance(cause, OSError) else GcFailureCode.VALUE_ERROR,
                type(cause).__module__ + "." + type(cause).__qualname__, str(cause),
                cause.errno if isinstance(cause, OSError) else None,
                getattr(cause, "winerror", None) if isinstance(cause, OSError) else None)
            if (failure.code, failure.exception_type, failure.message, failure.errno, failure.winerror) != expected:
                raise ValueError("GC failure does not match cause")
        elif cause is not None:
            raise ValueError("cause is only valid for GC_FAILED")
        level = to_logging_level(_LEVELS[record.activity])
        fields = record.model_dump(mode="json")
        if record.gc_failure is not None:
            fields["gc_failure"] = record.gc_failure.model_dump(mode="json", exclude={"message"})
        try:
            _LOGGER.log(level, "artifacts | %s | operation_id=%s",
                        record.activity.value, record.operation_id, extra=fields,
                        exc_info=(type(cause), cause, cause.__traceback__) if cause is not None else None)
        except UnknownLogConsumerError:
            raise
        except Exception:
            # Logging failure must not turn a sealed/deleted artifact into a refusal.
            return
