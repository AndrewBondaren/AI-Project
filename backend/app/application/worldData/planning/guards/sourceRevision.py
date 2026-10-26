"""Pure source revision check; authoritative reads/publication belong to the caller."""

from app.dataModel.planning.identity.planKey import StateViewRevision
from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningView


class SurfacePlanningStale(ValueError):
    def __init__(self, expected: StateViewRevision, actual: StateViewRevision) -> None:
        self.expected, self.actual = expected, actual
        super().__init__("surface source changed before publication")


def require_current_source(captured: SurfacePlanningView, current: SurfacePlanningView) -> None:
    if captured.world_uid != current.world_uid or captured.revision != current.revision:
        raise SurfacePlanningStale(captured.revision, current.revision)
