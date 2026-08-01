"""R36m/n: outward ``L_eff`` from world ``relief_grade_obstacle_policy``.

Caller measures ``free_gap`` (free cells until obstacle). This module only
applies the world setting — no footprint scan.
"""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.worldRow import relief_grade_obstacle_policy
from app.dataModel.terrain.relief.enums import ReliefGradeObstaclePolicy


def outward_length(
    *,
    world: Any,
    requested_length: int,
    free_gap: int,
) -> int:
    """Bake/runtime: resolve policy from ``world``, then ``L_eff``.

    ``L_eff < 1`` → caller skips grade on that strip.
    """
    policy = relief_grade_obstacle_policy(world)
    return policy.effective_outward_length(requested_length, free_gap)


def outward_length_for_policy(
    policy: ReliefGradeObstaclePolicy,
    *,
    requested_length: int,
    free_gap: int,
) -> int:
    """Same ``L_eff`` formula when policy is already resolved (tests / callers)."""
    return policy.effective_outward_length(requested_length, free_gap)
