"""Explicit Open Water source type IDs and admitted diagnostic pairs."""
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import PlanScopeKind
from app.dataModel.planning.identity.planKey import WorldPlanScope
from app.dataModel.planning.identity.planKey import RegionPlanScope
from app.dataModel.planning.identity.planKey import PlanKey
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.hydrology.query.source import WaterMembershipRun
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMappingEntry
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource
from app.dataModel.hydrology import waterDiagnostics
from app.dataModel.hydrology.declaredRiver import HydrologyMouth
from app.dataModel.hydrology.riverRouting import RiverPlanDiagnostic, RiverRouteDiagnostic, RiverRoutingCode, RiverRoutingFailure
from app.dataModel.hydrology.waterKindMismatchIssue import HydrologyMaterializationCode, WaterKindMismatchIssue
from app.dataModel.fields.validatedFieldPath import (
    FieldSegment,
    IndexSegment,
    KeySegment,
    ModelIdentity,
    ValidatedFieldPath,
    VariantSegment,
)


from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic

SOURCE_BINDINGS = (
    (23, HydrologyCellRole, CanonicalTypeKind.ENUM),
    (41, BasinKind, CanonicalTypeKind.ENUM),
    (53, WorldTopology, CanonicalTypeKind.RECORD),
    (54, WorldTopologyMode, CanonicalTypeKind.ENUM),
    (55, WorldBounds, CanonicalTypeKind.RECORD),
    (80, HydrologyConnectionType, CanonicalTypeKind.ENUM),
    (89, HydrologyMouth, CanonicalTypeKind.RECORD),
    (94, PlanRef, CanonicalTypeKind.RECORD),
    (95, PlanKey, CanonicalTypeKind.RECORD),
    (96, WorldPlanScope, CanonicalTypeKind.RECORD),
    (97, PlanScopeKind, CanonicalTypeKind.ENUM),
    (98, RegionPlanScope, CanonicalTypeKind.RECORD),
    (101, PlanDependency, CanonicalTypeKind.RECORD),
    (105, PlanDiagnostic, CanonicalTypeKind.RECORD),
    (111, PlanDiagnosticDisposition, CanonicalTypeKind.ENUM),
    (119, CoordinateSpace, CanonicalTypeKind.ENUM),
    (150, MapCellHydrology, CanonicalTypeKind.RECORD),
    (151, HydrologyShoreKind, CanonicalTypeKind.ENUM),
    (152, RiverDrainageLink, CanonicalTypeKind.RECORD),
    (153, WaterBody, CanonicalTypeKind.RECORD),
    (154, PhysicalWaterUnion, CanonicalTypeKind.RECORD),
    (226, SourceBodyMapping, CanonicalTypeKind.RECORD),
    (227, SourceBodyMappingEntry, CanonicalTypeKind.RECORD),
    (238, RegionCoverage, CanonicalTypeKind.RECORD),
    (239, CoverageSpan, CanonicalTypeKind.RECORD),
    (283, FineSurfaceWindow, CanonicalTypeKind.RECORD),
    (303, ValidatedFieldPath, CanonicalTypeKind.RECORD),
    (304, ModelIdentity, CanonicalTypeKind.RECORD),
    (305, FieldSegment, CanonicalTypeKind.RECORD),
    (306, VariantSegment, CanonicalTypeKind.RECORD),
    (307, IndexSegment, CanonicalTypeKind.RECORD),
    (308, KeySegment, CanonicalTypeKind.RECORD),
    (323, WaterKindMismatchIssue, CanonicalTypeKind.RECORD),
    (324, HydrologyMaterializationCode, CanonicalTypeKind.ENUM),
    (325, RiverRouteDiagnostic, CanonicalTypeKind.RECORD),
    (326, RiverRoutingCode, CanonicalTypeKind.ENUM),
    (327, RiverRoutingFailure, CanonicalTypeKind.ENUM),
    (328, RiverPlanDiagnostic, CanonicalTypeKind.RECORD),
    (329, waterDiagnostics.WaterDiagnosticCode, CanonicalTypeKind.ENUM),
    (330, waterDiagnostics.WaterPuddle, CanonicalTypeKind.RECORD),
    (331, waterDiagnostics.WaterCannotHold, CanonicalTypeKind.RECORD),
    (332, waterDiagnostics.WaterTerrainUnresolved, CanonicalTypeKind.RECORD),
    (333, waterDiagnostics.WaterNoOceanDepression, CanonicalTypeKind.RECORD),
    (334, waterDiagnostics.WaterLevelSpill, CanonicalTypeKind.RECORD),
    (335, waterDiagnostics.WaterLevelSuperseded, CanonicalTypeKind.RECORD),
    (336, waterDiagnostics.WaterWorldOcean, CanonicalTypeKind.RECORD),
    (338, waterDiagnostics.WaterPuddleDiagnostic, CanonicalTypeKind.RECORD),
    (339, waterDiagnostics.WaterCannotHoldDiagnostic, CanonicalTypeKind.RECORD),
    (340, waterDiagnostics.WaterTerrainUnresolvedDiagnostic, CanonicalTypeKind.RECORD),
    (341, waterDiagnostics.WaterNoOceanDepressionDiagnostic, CanonicalTypeKind.RECORD),
    (342, waterDiagnostics.WaterLevelSpillDiagnostic, CanonicalTypeKind.RECORD),
    (343, waterDiagnostics.WaterLevelSupersededDiagnostic, CanonicalTypeKind.RECORD),
    (344, waterDiagnostics.WaterWorldOceanDiagnostic, CanonicalTypeKind.RECORD),
    (60004, WaterMembershipRun, CanonicalTypeKind.RECORD),
    (60007, CanonicalOpenWaterSource, CanonicalTypeKind.RECORD),
    (60008, PlanEnvelope[CanonicalOpenWaterSource], CanonicalTypeKind.RECORD),
)
OPEN_WATER_SOURCE_SCHEMA_V1 = CanonicalSchemaManifest(entries=tuple(
    RegisteredTypeEntry(type_id=i, python_type=t, kind=k) for i, t, k in SOURCE_BINDINGS))

# The envelope annotation is intentionally open. Source v1 owns this exact subset.
DIAGNOSTIC_FACTS = {
    PlanDiagnostic: WaterKindMismatchIssue,
    RiverPlanDiagnostic: RiverRouteDiagnostic,
    waterDiagnostics.WaterPuddleDiagnostic: waterDiagnostics.WaterPuddle,
    waterDiagnostics.WaterCannotHoldDiagnostic: waterDiagnostics.WaterCannotHold,
    waterDiagnostics.WaterTerrainUnresolvedDiagnostic: waterDiagnostics.WaterTerrainUnresolved,
    waterDiagnostics.WaterNoOceanDepressionDiagnostic: waterDiagnostics.WaterNoOceanDepression,
    waterDiagnostics.WaterLevelSpillDiagnostic: waterDiagnostics.WaterLevelSpill,
    waterDiagnostics.WaterLevelSupersededDiagnostic: waterDiagnostics.WaterLevelSuperseded,
    waterDiagnostics.WaterWorldOceanDiagnostic: waterDiagnostics.WaterWorldOcean,
}
