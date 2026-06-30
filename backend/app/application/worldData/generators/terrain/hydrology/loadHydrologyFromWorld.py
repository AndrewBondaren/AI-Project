"""Load world.hydrology policy — D HY-1b."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.loggingHelpers import warn_once


def load_hydrology_from_world(world: Any) -> dict:
    """Return surface hydrology policy dict; empty if unset."""
    raw = getattr(world, "hydrology", None) or {}
    return raw if isinstance(raw, dict) else {}


def load_caves_hydrology_from_world(world: Any) -> dict:
    """Cave hydrology stub — U12 out of scope; read only for forward compat."""
    caves = getattr(world, "caves", None) or {}
    if not isinstance(caves, dict):
        return {}
    hyd = caves.get("hydrology") or {}
    return hyd if isinstance(hyd, dict) else {}


def is_hydrology_enabled(world: Any) -> bool:
    policy = load_hydrology_from_world(world)
    if "enabled" not in policy:
        uid = getattr(world, "world_uid", "?")
        warn_once(
            uid,
            "implicit_hydrology_enabled",
            "hydrology | world=%s enabled key missing; defaulting to true (import normalize target)",
        )
    return bool(policy.get("enabled", True))
