"""Non-recursive references to terminal dependency outcomes."""

from enum import StrEnum

from app.dataModel.placement.common import PlacementModel, PlacementUid


class PlacementOutcomeStatus(StrEnum):
    RESOLVED = "resolved"
    DISABLED = "disabled"
    UNRESOLVED = "unresolved"


class PlacementOutcomeRef(PlacementModel):
    region_uid: PlacementUid
    status: PlacementOutcomeStatus
