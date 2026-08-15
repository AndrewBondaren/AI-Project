"""Deterministic SHA256 seed helpers for relief pick / kind roll (RELIEF-T-40)."""

from __future__ import annotations

import hashlib


def _seeded_u64(key: str) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def seeded_u01(key: str) -> float:
    """Map ``key`` → uniform ``[0, 1)`` (first 8 bytes of SHA256)."""
    return _seeded_u64(key) / float(2**64)


def seeded_index(key: str, n: int) -> int:
    """Map ``key`` → index in ``[0, n)``."""
    if n < 1:
        raise ValueError(f"seeded_index n must be >= 1; got {n}")
    return _seeded_u64(key) % n
