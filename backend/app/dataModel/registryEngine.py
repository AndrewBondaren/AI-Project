"""Derive engine builtin rows from fixture + delta — POJO-D-4.

``engine = fixture order (extra replaces same key) + extra keys not in fixture``.
Optional ``drop`` removes fixture-only keys the engine slice does not carry.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


def engine_rows(
    fixture: Sequence[T],
    extra: Sequence[T],
    *,
    key: Callable[[T], str],
    drop: frozenset[str] = frozenset(),
) -> tuple[T, ...]:
    by_id: dict[str, T] = {key(row): row for row in fixture}
    appended: list[T] = []
    for row in extra:
        name = key(row)
        if name in by_id:
            by_id[name] = row
        else:
            appended.append(row)
    kept = [by_id[key(row)] for row in fixture if key(row) not in drop]
    return tuple(kept + appended)
