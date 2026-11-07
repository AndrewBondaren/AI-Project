"""Stable surface TLV registrations for app.dataModel.hydrology."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.hydrology import waterDiagnostics
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.boundaries.attachedCoastline import (
    AttachedCoastline,
    CoastlineBoundaryInput,
    CoastlineBoundaryPlan,
    CoastlinePart,
)
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, DeclaredRiverSegment, HydrologyMouth
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.enums.riverSystemRole import RiverSystemRole
from app.dataModel.hydrology.enums.riverSystemTopology import RiverSystemTopology
from app.dataModel.hydrology.enums.waterSide import WaterSide
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
from app.dataModel.hydrology.generation.waterGenerationSettings import (
    BodyWaterGenerationSettings,
    CategoryWaterGenerationSettings,
    WorldWaterGenerationSettings,
)
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.placement.placementFields import (
    WaterCategoryPlacementFields,
    WaterSourcePlacementFields,
)
from app.dataModel.hydrology.planning.hydrologyPlan import (
    CoastlinePaint,
    DeclaredWaterPaint,
    GeoHydrologyPlan,
    GeoHydrologyRoutesPlan,
    HydrologyPlan,
    HydrologyRoutesPlan,
    IntentRiverPaint,
    LakePaint,
    RiverPathSegment,
    RiverRoute,
    SegmentRiverPaint,
)
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import (
    HydrologyAnchorInput,
    HydrologyFinalInput,
    HydrologyPlanInput,
)
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.planning.stages.openWaterPlan import (
    AssembledWater,
    FineWaterResult,
    MaterializedWater,
)
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import (
    HydrologyPlacementBehaviorInputs,
    HydrologyPlacementGateInputs,
    HydrologyPolicyFacts,
    HydrologyProceduralExtentFacts,
    HydrologyProceduralGenerationInputs,
)
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.hydrology.riverRouting import (
    RiverPlanDiagnostic,
    RiverRouteDiagnostic,
    RiverRoutingCode,
    RiverRoutingFailure,
)
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy, RiverTypeClassify
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.shore import HydrologyShoreDefaults
from app.dataModel.hydrology.sources.proceduralWaterSource import ProceduralWaterSource
from app.dataModel.hydrology.sources.waterDesignSource import (
    AuthoredBasinSource,
    AuthoredLakeSource,
    CoastlineWaterSource,
    ProceduralSource,
    WaterDesignSourceKind,
)
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.waterKindMismatchIssue import HydrologyMaterializationCode, WaterKindMismatchIssue
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, PolicyReason, ValueSelectionDecision
from app.dataModel.spatial.grid.coordinateTypes import FineXY, SurfaceGridCoord
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (23, HydrologyCellRole, CanonicalTypeKind.ENUM),
    (29, HydrologySeasPolicy, CanonicalTypeKind.RECORD),
    (30, HydrologyBands, CanonicalTypeKind.RECORD),
    (31, HydrologyShoreDefaults, CanonicalTypeKind.RECORD),
    (32, HydrologyLakesPolicy, CanonicalTypeKind.RECORD),
    (33, DeclaredBasin, CanonicalTypeKind.RECORD),
    (41, BasinKind, CanonicalTypeKind.ENUM),
    (47, DeclaredCoastline, CanonicalTypeKind.RECORD),
    (48, WaterSide, CanonicalTypeKind.ENUM),
    (49, HydrologyWaypoint, CanonicalTypeKind.RECORD),
    (50, DeclaredLake, CanonicalTypeKind.RECORD),
    (80, HydrologyConnectionType, CanonicalTypeKind.ENUM),
    (81, HydrologyPlanInput, CanonicalTypeKind.RECORD),
    (82, HydrologyScope, CanonicalTypeKind.ENUM),
    (83, HydrologyRiversPolicy, CanonicalTypeKind.RECORD),
    (84, RiverTypeClassify, CanonicalTypeKind.RECORD),
    (85, DeclaredRiver, CanonicalTypeKind.RECORD),
    (86, RiverSystemRole, CanonicalTypeKind.ENUM),
    (87, RiverSystemTopology, CanonicalTypeKind.ENUM),
    (88, RiverDeclareMode, CanonicalTypeKind.ENUM),
    (89, HydrologyMouth, CanonicalTypeKind.RECORD),
    (90, DeclaredRiverSegment, CanonicalTypeKind.RECORD),
    (91, HydrologyAnchorInput, CanonicalTypeKind.RECORD),
    (92, HydrologyFinalInput, CanonicalTypeKind.RECORD),
    (148, PlanEnvelope[HydrologyRoutesPlan], CanonicalTypeKind.RECORD),
    (149, HydrologyRoutesPlan, CanonicalTypeKind.RECORD),
    (150, MapCellHydrology, CanonicalTypeKind.RECORD),
    (151, HydrologyShoreKind, CanonicalTypeKind.ENUM),
    (152, RiverDrainageLink, CanonicalTypeKind.RECORD),
    (153, WaterBody, CanonicalTypeKind.RECORD),
    (154, PhysicalWaterUnion, CanonicalTypeKind.RECORD),
    (155, RiverRoute[SurfaceGridCoord], CanonicalTypeKind.RECORD),
    (156, RiverPathSegment[SurfaceGridCoord], CanonicalTypeKind.RECORD),
    (157, RiverRoute[FineXY], CanonicalTypeKind.RECORD),
    (158, RiverPathSegment[FineXY], CanonicalTypeKind.RECORD),
    (159, DeclaredWaterPaint, CanonicalTypeKind.RECORD),
    (160, LakePaint, CanonicalTypeKind.RECORD),
    (161, CoastlinePaint, CanonicalTypeKind.RECORD),
    (162, SegmentRiverPaint, CanonicalTypeKind.RECORD),
    (163, IntentRiverPaint, CanonicalTypeKind.RECORD),
    (164, PlanEnvelope[HydrologyPlan], CanonicalTypeKind.RECORD),
    (165, HydrologyPlan, CanonicalTypeKind.RECORD),
    (166, CoastlinePurpose, CanonicalTypeKind.ENUM),
    (225, GeoHydrologyPlan, CanonicalTypeKind.RECORD),
    (226, SourceBodyMapping, CanonicalTypeKind.RECORD),
    (227, SourceBodyMappingEntry, CanonicalTypeKind.RECORD),
    (228, WaterGenerationCategory, CanonicalTypeKind.ENUM),
    (229, HydrologyExecutionMode, CanonicalTypeKind.ENUM),
    (230, WaterPolicyReason, CanonicalTypeKind.ENUM),
    (231, ValueSelectionDecision[HydrologyExecutionMode, WaterPolicyReason], CanonicalTypeKind.RECORD),
    (232, PolicyReason[WaterPolicyReason], CanonicalTypeKind.RECORD),
    (233, PlanEnvelope[GeoHydrologyPlan], CanonicalTypeKind.RECORD),
    (241, WorldWaterGenerationSettings, CanonicalTypeKind.RECORD),
    (242, WaterGenerationDefaults, CanonicalTypeKind.RECORD),
    (243, AuthoredBasinSource, CanonicalTypeKind.RECORD),
    (244, WaterDesignSourceKind, CanonicalTypeKind.ENUM),
    (245, AuthoredLakeSource, CanonicalTypeKind.RECORD),
    (246, CoastlineWaterSource, CanonicalTypeKind.RECORD),
    (247, ProceduralSource, CanonicalTypeKind.RECORD),
    (248, ProceduralWaterSource, CanonicalTypeKind.RECORD),
    (249, BodyWaterGenerationSettings, CanonicalTypeKind.RECORD),
    (251, GeoHydrologyPlanInput, CanonicalTypeKind.RECORD),
    (252, CoastlineBoundaryInput, CanonicalTypeKind.RECORD),
    (272, WaterSourceMetadata, CanonicalTypeKind.RECORD),
    (273, ObjectAdmissionDecision[DesignedWaterStrategyKind, WaterPolicyReason], CanonicalTypeKind.RECORD),
    (276, PlanEnvelope[GeoHydrologyRoutesPlan], CanonicalTypeKind.RECORD),
    (277, GeoHydrologyRoutesPlan, CanonicalTypeKind.RECORD),
    (278, PlanEnvelope[CoastlineBoundaryPlan], CanonicalTypeKind.RECORD),
    (279, CoastlineBoundaryPlan, CanonicalTypeKind.RECORD),
    (280, AttachedCoastline, CanonicalTypeKind.RECORD),
    (281, CoastlinePart, CanonicalTypeKind.RECORD),
    (282, CategoryWaterGenerationSettings, CanonicalTypeKind.RECORD),
    (285, MaterializedWater, CanonicalTypeKind.RECORD),
    (286, AssembledWater, CanonicalTypeKind.RECORD),
    (287, PlanEnvelope[FineWaterResult], CanonicalTypeKind.RECORD),
    (290, FineRiverPlan, CanonicalTypeKind.RECORD),
    (291, PlanEnvelope[FineRiverPlan], CanonicalTypeKind.RECORD),
    (297, CoarseRiverPlan, CanonicalTypeKind.RECORD),
    (314, WaterSourcePlacementFields, CanonicalTypeKind.RECORD),
    (315, WaterCategoryPlacementFields, CanonicalTypeKind.RECORD),
    (316, HydrologyPlacementBehaviorInputs, CanonicalTypeKind.RECORD),
    (317, HydrologyPlacementGateInputs, CanonicalTypeKind.RECORD),
    (318, HydrologyPolicyFacts, CanonicalTypeKind.RECORD),
    (319, HydrologyProceduralGenerationInputs, CanonicalTypeKind.RECORD),
    (320, HydrologyProceduralExtentFacts, CanonicalTypeKind.RECORD),
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
)
