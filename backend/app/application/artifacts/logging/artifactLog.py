"""Artifact staging/holder/GC events through the project's shared logging facade."""

import logging

from app.core.logLevel import LogLevel, to_logging_level
from app.dataModel.artifacts.events import ArtifactLogActivity, ArtifactLogRecord


_LOGGER = logging.getLogger("app.artifacts")
_LEVELS: dict[ArtifactLogActivity, LogLevel] = {
    ArtifactLogActivity.ARTIFACT_SEALED: LogLevel.DEBUG,
    ArtifactLogActivity.LEASE_RELEASED: LogLevel.INFO,
    ArtifactLogActivity.GC_DELETED: LogLevel.INFO,
    ArtifactLogActivity.GC_FAILED: LogLevel.ERROR,
}


class ArtifactLifecycleLog:
    __slots__ = ()

    def emit(self, record: ArtifactLogRecord) -> None:
        """Submit a reported storage fact without executing storage work or adding a world UID."""
        if type(record) is not ArtifactLogRecord:
            raise TypeError("expected a typed ArtifactLogRecord")
        record = ArtifactLogRecord.model_validate(record, strict=True)
        level = to_logging_level(_LEVELS[record.activity])
        fields = record.model_dump(mode="json")
        try:
            _LOGGER.log(level, "artifacts | %s | operation_id=%s",
                        record.activity.value, record.operation_id, extra=fields)
        except Exception:
            # Logging failure must not turn a sealed/deleted artifact into a refusal.
            return
