"""JSON formatting shared by domain sinks and generation transcripts."""
import json
import logging
from datetime import datetime, timezone

from app.core.logging.context import request_id_var

# Use stdlib's schema directly, without including custom LogRecordFactory extras.
_RECORD_BUILTINS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)))
# Formatter adds these lazily; they are not LogRecord constructor attributes.
_FORMATTER_FIELDS = frozenset({"message", "asctime"})

class JsonLogFormatter(logging.Formatter):
    """One JSON object per line — domain files and generation transcript."""

    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key not in _RECORD_BUILTINS and key not in _FORMATTER_FIELDS and not key.startswith("_"):
                obj[key] = val
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)
