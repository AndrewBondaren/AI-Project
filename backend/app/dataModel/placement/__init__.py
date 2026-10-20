"""Shared placement contract — tz_map_light_bake § Placement P1; no resolver."""

from app.dataModel.placement.batch import PlacementBatch
from app.dataModel.placement.common import (
    AbsoluteMovement, DependencyRelation, OverlapRelation, PlacementMode,
    PlacementPhase, WaterPresence,
)
from app.dataModel.placement.intent import (
    PlacementDependency, PlacementIdentity, PlacementIntent, PlacementOverlap, PlacementSeparation,
)
from app.dataModel.placement.prepared import (
    CoastlinePlacementFact, PlacementCandidate, PlacementFootprint, PreparedPlacement,
)
from app.dataModel.placement.result import (
    PlacementBatchResult, PlacementDiagnostic, PlacementIssueCode, PlacementOutcome,
    ResolvedPlacement, UnresolvedPlacement,
)
from app.dataModel.placement.water import ResolvedWaterPlacement

__all__ = [
    "AbsoluteMovement", "CoastlinePlacementFact", "DependencyRelation", "OverlapRelation",
    "PlacementBatch", "PlacementBatchResult", "PlacementCandidate", "PlacementDependency",
    "PlacementDiagnostic", "PlacementFootprint", "PlacementIdentity", "PlacementIntent",
    "PlacementIssueCode", "PlacementMode", "PlacementOutcome", "PlacementOverlap",
    "PlacementPhase", "PlacementSeparation", "PreparedPlacement", "ResolvedPlacement",
    "ResolvedWaterPlacement", "UnresolvedPlacement", "WaterPresence",
]
