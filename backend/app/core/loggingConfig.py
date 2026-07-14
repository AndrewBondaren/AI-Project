import json
import logging
import logging.handlers
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


_RECORD_BUILTINS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName", "process",
    "processName", "message", "asctime", "taskName",
})


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line — shared by app.log and generation sinks."""

    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key not in _RECORD_BUILTINS and not key.startswith("_"):
                obj[key] = val
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)


# Back-compat alias
_JsonFormatter = JsonLogFormatter


def setup_logging(
    log_file: str = "logs/app.log",
    level: int = logging.INFO,
    logger_levels: dict[str, str] | None = None,
) -> None:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    formatter = JsonLogFormatter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    rotating = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    rotating.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(rotating)

    for name, lvl in (logger_levels or {}).items():
        logging.getLogger(name).setLevel(lvl)
