"""Stable placement exports, loaded lazily to keep leaf policy imports acyclic."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    modules = {
        "batch": ("PlacementBatch",),
        "common": ("AbsoluteMovement", "DependencyRelation", "OverlapRelation", "PlacementMode", "PlacementPhase", "WaterPresence"),
        "intent": ("PlacementDependency", "PlacementIdentity", "PlacementIntent", "PlacementOverlap", "PlacementSeparation"),
        "prepared": ("CoastlinePlacementFact", "PlacementCandidate", "PlacementFootprint", "PreparedPlacement"),
        "result": ("PlacementBatchResult", "PlacementDiagnostic", "PlacementIssueCode", "PlacementOutcome", "ResolvedPlacement", "UnresolvedPlacement"),
        "water": ("ResolvedWaterPlacement",),
    }
    module = next(module for module, names in modules.items() if name in names)
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
