"""Bake / relief deterministic seed helper (RELIEF-T-17)."""

from __future__ import annotations

from typing import Any

from app.ids import seed_root


def bake_seed(world: Any) -> str:
    """SoT seed for relief pick / Mode D / shoulder grade until World has seed field."""
    uid = getattr(world, "world_uid", None)
    if uid:
        return seed_root(world)
    return "world"
