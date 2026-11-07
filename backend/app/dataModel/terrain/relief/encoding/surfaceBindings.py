"""Stable surface TLV registrations for app.dataModel.terrain.relief."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.materials.enums.materialSubstrateKind import MaterialSubstrateKind
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.policy.policyDecision import PolicyReason, ValueSelectionDecision
from app.dataModel.policy.policyFacts import KnownFact
from app.dataModel.spatial.grid.coordinateTypes import FineXY, SurfaceGridCoord
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.relief.bathymetry.floorProfile import (
    FieldFloorProfile,
    FloorProfileKind,
    SampledFloorProfile,
)
from app.dataModel.terrain.relief.enums import (
    ReliefConditionTerrain,
    ReliefContext,
    ReliefPickMode,
    ReliefSideKind,
    ReliefSlopePolicy,
)
from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import (
    MountainAnchorInput,
    ReliefPlanInput,
    RiverReliefInput,
    TerrainMergeEntry,
)
from app.dataModel.terrain.relief.planning.reliefPlan import (
    LightMountainCell,
    LightRavineCell,
    LightReliefPlan,
    MountainLayout,
    MountainTemplateInput,
    ReliefPlan,
    RiverBedRecord,
    RiverReliefPlan,
)
from app.dataModel.terrain.relief.reliefDeltaBand import ReliefDeltaBand
from app.dataModel.terrain.relief.reliefRoleCase import ReliefRoleCase
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.reliefTerrainCondition import ReliefTerrainCondition
from app.dataModel.terrain.relief.specs import ReliefSideSpec
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import (
    CoatingCellPlan,
    CoatingPlan,
    ShoreCoatingTarget,
    SurfaceAspect,
    SurfaceCoatingAction,
    SurfaceCoatingFacts,
    SurfaceCoatingReason,
    SurfaceSupportPlan,
)
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import (
    CoatingPlanInput,
    LandcoverSupportPolicy,
    MaterialSupportEntry,
    SurfaceSupportInput,
    TerrainSupportEntry,
)
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy, ReliefContextPickPolicy


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (56, ReliefPlanInput, CanonicalTypeKind.RECORD),
    (63, ReliefSideSpec, CanonicalTypeKind.RECORD),
    (64, ReliefSideKind, CanonicalTypeKind.ENUM),
    (68, ObjectReliefPickPolicy, CanonicalTypeKind.RECORD),
    (69, ReliefContextPickPolicy, CanonicalTypeKind.RECORD),
    (70, ReliefPickMode, CanonicalTypeKind.ENUM),
    (74, MountainAnchorInput, CanonicalTypeKind.RECORD),
    (75, MountainTemplateInput, CanonicalTypeKind.RECORD),
    (76, ReliefContext, CanonicalTypeKind.ENUM),
    (77, MountainSideRecipe, CanonicalTypeKind.RECORD),
    (78, TerrainMergeEntry, CanonicalTypeKind.RECORD),
    (79, RiverReliefInput, CanonicalTypeKind.RECORD),
    (136, BasinSpec, CanonicalTypeKind.RECORD),
    (137, PlanEnvelope[ReliefPlan], CanonicalTypeKind.RECORD),
    (138, ReliefPlan, CanonicalTypeKind.RECORD),
    (139, MountainLayout, CanonicalTypeKind.RECORD),
    (140, LightReliefPlan, CanonicalTypeKind.RECORD),
    (142, LightMountainCell, CanonicalTypeKind.RECORD),
    (143, LightRavineCell, CanonicalTypeKind.RECORD),
    (144, PlanEnvelope[RiverReliefPlan], CanonicalTypeKind.RECORD),
    (145, RiverReliefPlan, CanonicalTypeKind.RECORD),
    (146, RiverBedRecord[SurfaceGridCoord], CanonicalTypeKind.RECORD),
    (147, RiverBedRecord[FineXY], CanonicalTypeKind.RECORD),
    (167, SampledFloorProfile, CanonicalTypeKind.RECORD),
    (168, FieldFloorProfile, CanonicalTypeKind.RECORD),
    (169, FloorProfileKind, CanonicalTypeKind.ENUM),
    (183, ReliefConditionTerrain, CanonicalTypeKind.ENUM),
    (184, ReliefSlopePolicy, CanonicalTypeKind.ENUM),
    (185, ReliefDeltaBand, CanonicalTypeKind.RECORD),
    (186, ReliefRoleCase, CanonicalTypeKind.RECORD),
    (187, ReliefTemplate, CanonicalTypeKind.RECORD),
    (188, ReliefTerrainCondition, CanonicalTypeKind.RECORD),
    (189, LandcoverSupportPolicy, CanonicalTypeKind.RECORD),
    (190, MaterialSupportEntry, CanonicalTypeKind.RECORD),
    (191, SurfaceSupportInput, CanonicalTypeKind.RECORD),
    (192, TerrainSupportEntry, CanonicalTypeKind.RECORD),
    (199, SurfaceAspect, CanonicalTypeKind.ENUM),
    (200, SurfaceCoatingAction, CanonicalTypeKind.ENUM),
    (201, SurfaceCoatingReason, CanonicalTypeKind.ENUM),
    (202, SurfaceCoatingFacts, CanonicalTypeKind.RECORD),
    (203, SurfaceSupportPlan, CanonicalTypeKind.RECORD),
    (204, ShoreCoatingTarget, CanonicalTypeKind.RECORD),
    (205, CoatingCellPlan, CanonicalTypeKind.RECORD),
    (206, CoatingPlan, CanonicalTypeKind.RECORD),
    (207, CoatingPlanInput, CanonicalTypeKind.RECORD),
    (208, KnownFact[SurfaceAspect], CanonicalTypeKind.RECORD),
    (209, KnownFact[ReliefSideKind], CanonicalTypeKind.RECORD),
    (210, KnownFact[MaterialKey], CanonicalTypeKind.RECORD),
    (211, KnownFact[MaterialSubstrateKind], CanonicalTypeKind.RECORD),
    (212, KnownFact[ShoreCoatingTarget], CanonicalTypeKind.RECORD),
    (216, ValueSelectionDecision[SurfaceCoatingAction, SurfaceCoatingReason], CanonicalTypeKind.RECORD),
    (217, PolicyReason[SurfaceCoatingReason], CanonicalTypeKind.RECORD),
    (223, PlanEnvelope[SurfaceSupportPlan], CanonicalTypeKind.RECORD),
    (224, PlanEnvelope[CoatingPlan], CanonicalTypeKind.RECORD),
)
