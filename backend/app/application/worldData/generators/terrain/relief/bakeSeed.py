"""Bake / relief deterministic seed helper (RELIEF-T-17)."""

from __future__ import annotations

from typing import Any


def bake_seed(world: Any) -> str:
    """SoT seed for relief pick / Mode D / shoulder grade until World has seed field."""
    uid = getattr(world, "world_uid", None)
    if uid:
        return str(uid)
    return "world"
