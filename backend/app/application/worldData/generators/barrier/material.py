"""Barrier material resolution from barrier_template_registry."""

from __future__ import annotations

from random import Random

from app.application.worldData.generators.utils.materialResolver import resolve_material
from app.db.models.world import World


def pick_barrier_material(
    world:            World,
    barrier_template: dict,
    economic_tier:    str | None,
    rng:              Random,
    default:          str = "stone",
) -> str:
    pick_from = (barrier_template.get("wall_material") or {}).get("pick_from") or []
    if pick_from:
        return rng.choice(pick_from)
    return resolve_material(
        world, "wall", economic_tier, rng, default=default,
    )
