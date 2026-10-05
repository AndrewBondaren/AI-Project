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
    params: dict[str, tuple],
) -> None:
    """DEBUG per ``extend()`` boundary — level, link object types and
    the per-param handoff ``value parent=<src|none> child=<src|none>``:
    ``parent=none`` — the param is its own top parent; ``child=none`` —
    nothing fed it at this boundary (pure inheritance).

    ``params`` carries the raw resolution record per field —
    ``(value, inherited_source, new_source)``; the ``parent=``/``child=``
    presentation is shaped here, not in the engine.
    """
    formatted = {
        name: _format_handoff(value, inherited, source)
        for name, (value, inherited, source) in params.items()
    }
    logger.debug(
        "cascade scope | level=%s objects=%s params=%s",
        level,
        ",".join(objects) if objects else "-",
        formatted or "-",
        extra={
            "activity": "scope_resolve",
            "scope_level": level,
            "params": formatted or None,
        },
    )


def _format_handoff(value, inherited_source, source) -> str:
    parent = (
        f"{inherited_source[0].value}.{inherited_source[1]}"
        if inherited_source is not None
        else "none"
    )
    child = (
        f"{source[0].value}.{source[1]}"
        if source != inherited_source
        else "none"
    )
    return f"{value} parent={parent} child={child}"


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
