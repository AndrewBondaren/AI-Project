"""Load world.hydrology policy — D HY-1b."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.masterData import hydrology, hydrology_dict


def load_hydrology_from_world(world: Any) -> dict:
    """Return surface hydrology policy dict; canonical_empty when unset."""
    return hydrology_dict(world)


def load_caves_hydrology_from_world(world: Any) -> dict:
    """Cave hydrology stub — U12 out of scope; read only for forward compat."""
    caves = getattr(world, "caves", None) or {}
    if not isinstance(caves, dict):
        return {}
    hyd = caves.get("hydrology") or {}
    return hyd if isinstance(hyd, dict) else {}


def is_hydrology_enabled(world: Any) -> bool:
    policy = hydrology(world)
    if policy.enabled is None:
        uid = getattr(world, "world_uid", "?")
        warn_once(
            uid,
            "implicit_hydrology_enabled",
            "hydrology | world=%s enabled key missing; defaulting to true (import normalize target)",
        )
    return bool(policy.enabled if policy.enabled is not None else True)
