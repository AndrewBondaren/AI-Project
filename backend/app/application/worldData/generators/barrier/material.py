"""Barrier material resolution from barrier_template_registry."""

from __future__ import annotations

from random import Random

from app.application.worldData.generators.utils.materialResolver import resolve_material
from app.dataModel.structure.barrier.barrierTemplateEntry import BarrierTemplateEntry
from app.db.models.world import World


def pick_barrier_material(
    world:            World,
    barrier_template: BarrierTemplateEntry,
    economic_tier:    str | None,
    rng:              Random,
    default:          str = "stone",
) -> str:
    pick = barrier_template.wall_material
    if pick is not None and pick.pick_from:
        return rng.choice(pick.pick_from)
    return resolve_material(
        world, "wall", economic_tier, rng, default=default,
    )
