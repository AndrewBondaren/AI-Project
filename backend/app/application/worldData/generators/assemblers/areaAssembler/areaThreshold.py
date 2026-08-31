from dataclasses import dataclass
from enum import StrEnum

from app.dataModel.spatial.facing import Facing


class AreaThresholdKind(StrEnum):
    DOOR = "door"
    GATE = "gate"
    PARCEL_EDGE = "parcel_edge"


@dataclass
class AreaThreshold:
    """Стык улицы с участком. DTO only — no ray / clamp methods."""

    kind:  AreaThresholdKind
    cells: list[tuple[int, int]]
    z:     int
