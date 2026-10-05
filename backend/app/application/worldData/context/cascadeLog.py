"""Cascade log helper — docs/tz_logging.md cascade / cascadeLog.

Events: tz_cascade_context.md §4 «Логирование». Emission lives in the
engine (``contextResolver.extend``); this module only shapes records —
no ad-hoc ``getLogger`` for the same events elsewhere (L3/L5).
"""

from __future__ import annotations

import logging
from typing import Any

from app.dataModel.cascade.cascadeSpec import DefaultPolicy

logger = logging.getLogger(__name__)


def log_scope_resolve(
    *,
    level: str,
    objects: list[str],
    params: dict[str, str],
) -> None:
    """DEBUG per ``extend()`` boundary — level, link object types and
    the per-param handoff ``value parent=<src|none> child=<src|none>``:
    ``parent=none`` — the param is its own top parent; ``child=none`` —
    nothing fed it at this boundary (pure inheritance)."""
    logger.debug(
        "cascade scope | level=%s objects=%s params=%s",
        level,
        ",".join(objects) if objects else "-",
        params or "-",
        extra={
            "activity": "scope_resolve",
            "scope_level": level,
            "params": params or None,
        },
    )


def log_default_applied(
    *,
    param: str,
    level: str,
    policy: DefaultPolicy,
    value: Any,
) -> None:
    """Provisional domain default applied at a scope boundary.

    ``REGISTRY_MEDIAN`` warns once per chain (the engine dedupes
    re-warns on deeper empty scopes); quiet policies log at DEBUG.
    """
    emit = (
        logger.warning
        if policy is DefaultPolicy.REGISTRY_MEDIAN
        else logger.debug
    )
    emit(
        "cascade default | param=%s level=%s policy=%s value=%r",
        param,
        level,
        policy.value,
        value,
        extra={
            "activity": "default_applied",
            "param": param,
            "scope_level": level,
            "default_policy": policy.value,
            "value": value,
        },
    )
