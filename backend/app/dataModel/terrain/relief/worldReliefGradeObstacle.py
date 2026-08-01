"""World scalar ``relief_grade_obstacle_policy`` — tz_terrain_relief R36n.

Wire: string enum on ``worlds`` row (not nested JSON blob).
Consumers: ``relief_grade_obstacle_policy(world)`` via ``jsonValidation.worldRow``.
Wire projection / startup column sync: thin wrappers over
``app.dataModel.worldScalarWire`` (**JV-SCALARS-1**).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultEnumOnWire
from app.dataModel.terrain.relief.enums import ReliefGradeObstaclePolicy
from app.dataModel.worldScalarWire import (
    pojo_wire_keys,
    scalar_wire_from_mapping,
    validate_world_row_pojo_columns,
)


class WorldReliefGradeObstacleScalars(BaseModel):
    """Scalar relief obstacle field on ``worlds``."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-RELIEF-OBSTACLE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    relief_grade_obstacle_policy: DefaultEnumOnWire[ReliefGradeObstaclePolicy] = (
        ReliefGradeObstaclePolicy.TRUNCATE_SKIP
    )

    @classmethod
    def canonical_defaults(cls) -> WorldReliefGradeObstacleScalars:
        return cls()


RELIEF_OBSTACLE_SCALAR_WIRE_KEYS: frozenset[str] = pojo_wire_keys(
    WorldReliefGradeObstacleScalars,
)


def relief_obstacle_scalar_wire_from_mapping(source: Any) -> dict[str, Any]:
    """Project ``worlds`` row or wire dict → slice for ``resolve_model``."""
    return scalar_wire_from_mapping(RELIEF_OBSTACLE_SCALAR_WIRE_KEYS, source)


def validate_world_row_relief_obstacle_columns(world_cls: type) -> None:
    """Startup assert: POJO fields ⊆ ``World`` columns."""
    validate_world_row_pojo_columns(
        world_cls,
        WorldReliefGradeObstacleScalars,
        label="relief obstacle",
    )
