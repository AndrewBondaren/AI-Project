"""Declare ∪ autoresolve merge — tz_map_light_bake § MaskDomain materialize."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


def merge_declare_over_auto(
    declared: Sequence[T],
    auto: Sequence[T],
    *,
    key: Callable[[T], object],
) -> list[T]:
    """Declare wins: auto entries whose ``key`` collides with declare are dropped."""
    declared_list = list(declared)
    seen = {key(item) for item in declared_list}
    out = list(declared_list)
    for item in auto:
        k = key(item)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out
