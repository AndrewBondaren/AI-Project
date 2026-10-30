"""Snapshot lifecycle events through the shared logging facade, without local sinks."""

import logging

from app.core.logLevel import LogLevel, to_logging_level
from app.dataModel.worldSnapshot.events import SnapshotLogActivity, SnapshotLogRecord


_LOGGER = logging.getLogger("app.snapshot")
_LEVELS: dict[SnapshotLogActivity, LogLevel] = {
    SnapshotLogActivity.APPLY_STARTED: LogLevel.DEBUG,
    SnapshotLogActivity.APPLY_COMMITTED: LogLevel.INFO,
    SnapshotLogActivity.APPLY_CONFLICT: LogLevel.WARNING,
    SnapshotLogActivity.APPLY_REJECTED: LogLevel.WARNING,
    SnapshotLogActivity.APPLY_FAILED: LogLevel.ERROR,
    SnapshotLogActivity.APPLY_OUTCOME_UNKNOWN: LogLevel.ERROR,
    SnapshotLogActivity.OPERATION_BUSY: LogLevel.DEBUG,
    SnapshotLogActivity.OPERATION_RECOVERED: LogLevel.INFO,
}


class SnapshotLifecycleLog:
    __slots__ = ()

    def emit(self, record: SnapshotLogRecord) -> None:
        """Caller confirms COMMIT before success and selects RECOVERED for terminal retries.

        One call submits one event; this emitter does not keep operation history
        or deduplicate publications. Logging delivery cannot change a durable outcome.
        """
        if type(record) is not SnapshotLogRecord:
            raise TypeError("expected a typed SnapshotLogRecord")
        record = SnapshotLogRecord.model_validate(record, strict=True)
        level = to_logging_level(_LEVELS[record.activity])
        fields = record.model_dump(mode="json")
        try:
            _LOGGER.log(level, "snapshot | %s | operation_id=%s",
                        record.activity.value, record.operation_id, extra=fields)
        except Exception:
            # Best effort only: no retry, secondary error event or state change.
            return
