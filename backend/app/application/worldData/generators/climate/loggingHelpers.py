"""Shared climate logging — warn-once dedupe per (world_uid, reason)."""

from app.core.logging.contracts import LogConsumer
from app.core.logging.consumers import get_consumer_logger

logger = get_consumer_logger(LogConsumer.CLIMATE)

_warned: set[tuple[str, str]] = set()
_debugged: set[tuple[str, str]] = set()


def warn_once(world_uid: str, reason: str, msg: str, *args: object) -> None:
    key = (world_uid, reason)
    if key in _warned:
        return
    _warned.add(key)
    logger.warning(msg, world_uid, *args)


def debug_once(world_uid: str, reason: str, msg: str, *args: object) -> None:
    key = (world_uid, reason)
    if key in _debugged:
        return
    _debugged.add(key)
    logger.debug(msg, world_uid, *args)
