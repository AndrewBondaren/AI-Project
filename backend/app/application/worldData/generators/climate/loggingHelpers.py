"""Shared climate logging — warn-once dedupe per (world_uid, reason)."""

import logging

logger = logging.getLogger(__name__)

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
