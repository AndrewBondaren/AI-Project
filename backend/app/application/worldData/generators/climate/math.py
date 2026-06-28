"""Shared climate math helpers (DR-5 / CL-12)."""

import hashlib
import math

from app.db.models.world import World


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def dist_euclidean(x1: int, y1: int, x2: int, y2: int) -> float:
    return math.hypot(x1 - x2, y1 - y2)


def dist_sq(x1: int, y1: int, x2: int, y2: int) -> int:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2


def world_seed(world: World) -> int:
    return int(hashlib.md5(world.world_uid.encode()).hexdigest()[:8], 16)
