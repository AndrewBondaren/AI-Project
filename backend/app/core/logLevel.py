import logging
from enum import StrEnum


class LogLevel(StrEnum):
    DEBUG   = "debug"
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"
    OFF     = "off"


def to_logging_level(log_level: LogLevel) -> int:
    return {
        LogLevel.DEBUG:   logging.DEBUG,
        LogLevel.INFO:    logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR:   logging.ERROR,
        LogLevel.OFF:     logging.CRITICAL + 1,
    }[log_level]
