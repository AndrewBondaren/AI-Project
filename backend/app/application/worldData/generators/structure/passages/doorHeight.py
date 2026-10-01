"""Shared entry/connection door-height contract (§3.7)."""
import logging
from math import floor

from app.application.worldData.generators.structure.errors import GenerationError
from app.dataModel.structure.building.structureTemplate import (
    DEFAULT_DOOR_HEIGHT_MAX, DEFAULT_DOOR_HEIGHT_RATIO, StructureTemplate,
)

logger = logging.getLogger(__name__)


def resolve_door_height(
    z_height: int,
    explicit: int | None,
    passage_height: int,
    template: StructureTemplate | None,
    *,
    context: str,
) -> int:
    uid = template.system_name if template is not None else "<unspecified>"
    if explicit is not None and explicit >= passage_height:
        height = explicit
    else:
        if explicit is not None:
            logger.error(
                "Structure '%s', %s: door_height=%d below passage_height=%d — auto-resolve",
                uid, context, explicit, passage_height,
            )
        ratio = template.door_height_ratio if template is not None else DEFAULT_DOOR_HEIGHT_RATIO
        cap = template.door_height_max if template is not None else DEFAULT_DOOR_HEIGHT_MAX
        height = z_height - 1 if z_height <= 3 else min(floor(z_height * ratio), cap)
        height = max(height, passage_height)
    if not passage_height <= height < z_height:
        raise GenerationError(
            f"Structure '{uid}', {context}: door_height={height} "
            f"must satisfy {passage_height} <= door_height < z_height={z_height}"
        )
    return height
