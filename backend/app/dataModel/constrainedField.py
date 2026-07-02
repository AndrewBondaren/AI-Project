"""Readable names for Pydantic ``Field`` numeric bounds.

Pydantic wire kwargs stay ``ge`` / ``gt`` / ``le`` / ``lt``; this module maps:

- ``greater_equals`` → ``ge``
- ``greater`` → ``gt``
- ``lesser_equals`` → ``le``
- ``lesser`` → ``lt``
"""

from __future__ import annotations

from typing import Any

from pydantic import Field


def constrained_field(
    default: Any = ...,
    *,
    greater_equals: float | int | None = None,
    greater: float | int | None = None,
    lesser_equals: float | int | None = None,
    lesser: float | int | None = None,
    **kwargs: Any,
) -> Any:
    """``Field(...)`` with readable bound names instead of ``ge``/``gt``/``le``/``lt``."""
    bounds: dict[str, float | int] = {}
    if greater_equals is not None:
        bounds["ge"] = greater_equals
    if greater is not None:
        bounds["gt"] = greater
    if lesser_equals is not None:
        bounds["le"] = lesser_equals
    if lesser is not None:
        bounds["lt"] = lesser
    return Field(default, **bounds, **kwargs)
