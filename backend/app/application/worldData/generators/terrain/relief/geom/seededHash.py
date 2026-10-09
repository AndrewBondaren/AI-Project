"""Deterministic relief pick / kind-roll streams (RELIEF-T-40, DET-1).

Thin typed helpers over ``seed_*`` — consumers pass ``world_seed`` and
named keys; the canonical string lives in ``worldData/ids`` only.
"""

from __future__ import annotations

from typing import Any

from app.ids import UidKind, seed_rng


def seeded_u01(world_seed: str, kind: UidKind, **keys: Any) -> float:
    """Uniform ``[0, 1)`` from the scoped stream."""
    return seed_rng(world_seed, kind, **keys).random()


def seeded_index(world_seed: str, kind: UidKind, n: int, **keys: Any) -> int:
    """Index in ``[0, n)`` from the scoped stream."""
    if n < 1:
        raise ValueError(f"seeded_index n must be >= 1; got {n}")
    return seed_rng(world_seed, kind, **keys).randrange(n)
