"""Stable surface TLV registrations for app.dataModel.placement."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.placement.common import (
    AbsoluteMovement,
    DependencyRelation,
    OverlapRelation,
    PlacementMode,
    WaterPresence,
)
from app.dataModel.placement.intent import (
    PlacementDependency,
    PlacementIdentity,
    PlacementIntent,
    PlacementOverlap,
    PlacementSeparation,
)
from app.dataModel.placement.lifecycle.causal import PlacementOutcomeRef, PlacementOutcomeStatus
from app.dataModel.placement.prepared import (
    CoastlinePlacementFact,
    PlacementCandidate,
    PlacementFootprint,
    PreparedPlacement,
    PreparedPlacementV2,
)
from app.dataModel.placement.result import (
    DisabledPlacement,
    PlacementBatchResultV2,
    PlacementDiagnostic,
    PlacementIssueCode,
    ResolvedPlacement,
    ResolvedPlacementV2,
    UnresolvedPlacementV2,
)
from app.dataModel.placement.water import ResolvedWaterPlacement
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (120, ResolvedWaterPlacement, CanonicalTypeKind.RECORD),
    (121, ResolvedPlacement, CanonicalTypeKind.RECORD),
    (122, PreparedPlacement, CanonicalTypeKind.RECORD),
    (123, PlacementIntent, CanonicalTypeKind.RECORD),
    (124, PlacementIdentity, CanonicalTypeKind.RECORD),
    (125, PlacementMode, CanonicalTypeKind.ENUM),
    (126, AbsoluteMovement, CanonicalTypeKind.ENUM),
    (127, PlacementDependency, CanonicalTypeKind.RECORD),
    (128, DependencyRelation, CanonicalTypeKind.ENUM),
    (129, PlacementOverlap, CanonicalTypeKind.RECORD),
    (130, OverlapRelation, CanonicalTypeKind.ENUM),
    (131, PlacementSeparation, CanonicalTypeKind.RECORD),
    (132, PlacementCandidate, CanonicalTypeKind.RECORD),
    (133, PlacementFootprint, CanonicalTypeKind.RECORD),
    (134, CoastlinePlacementFact, CanonicalTypeKind.RECORD),
    (135, WaterPresence, CanonicalTypeKind.ENUM),
    (262, ResolvedPlacementV2, CanonicalTypeKind.RECORD),
    (263, PreparedPlacementV2, CanonicalTypeKind.RECORD),
    (266, DisabledPlacement, CanonicalTypeKind.RECORD),
    (267, PlacementOutcomeRef, CanonicalTypeKind.RECORD),
    (268, PlacementOutcomeStatus, CanonicalTypeKind.ENUM),
    (269, PlacementDiagnostic, CanonicalTypeKind.RECORD),
    (270, PlacementIssueCode, CanonicalTypeKind.ENUM),
    (271, UnresolvedPlacementV2, CanonicalTypeKind.RECORD),
    (288, PlacementBatchResultV2, CanonicalTypeKind.RECORD),
    (289, PlanEnvelope[PlacementBatchResultV2], CanonicalTypeKind.RECORD),
)
