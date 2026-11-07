"""Stable surface TLV registrations for app.application.worldData.planning."""

from app.application.worldData.planning.contracts.surfacePlanBundle import GeoSurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import (
    GeoSurfacePlanningView,
    SurfacePlanningViewKind,
)
from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import PlanKey, PlanScopeKind, RegionPlanScope, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (94, PlanRef, CanonicalTypeKind.RECORD),
    (95, PlanKey, CanonicalTypeKind.RECORD),
    (96, WorldPlanScope, CanonicalTypeKind.RECORD),
    (97, PlanScopeKind, CanonicalTypeKind.ENUM),
    (98, RegionPlanScope, CanonicalTypeKind.RECORD),
    (99, PlanContractRegistry, CanonicalTypeKind.RECORD),
    (100, PlanContractMetadata, CanonicalTypeKind.RECORD),
    (101, PlanDependency, CanonicalTypeKind.RECORD),
    (105, PlanDiagnostic, CanonicalTypeKind.RECORD),
    (111, PlanDiagnosticDisposition, CanonicalTypeKind.ENUM),
    (234, GeoSurfacePlanningView, CanonicalTypeKind.RECORD),
    (235, SurfacePlanningViewKind, CanonicalTypeKind.ENUM),
    (255, GeoSurfacePlanBundle, CanonicalTypeKind.RECORD),
)
