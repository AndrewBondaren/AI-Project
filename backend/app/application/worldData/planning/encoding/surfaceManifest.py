"""Stable surface TLV type declarations; moving modules never changes type IDs."""

from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, RegisteredTypeEntry, CanonicalTypeKind

from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput as _MClimateBaseInput
from app.dataModel.spatial.grid.gridBBox import GridBBox as _MGridBBox
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode as _MClimatePoleMode
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset as _MClimatePolePreset
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry as _MWorldClimateZoneRegistry
from app.dataModel.climate.climateZone.climateZoneEntry import ClimateZoneEntry as _MClimateZoneEntry
from app.dataModel.climate.planning.inputs.climateBaseInput import ManualPoleInput as _MManualPoleInput
from app.dataModel.climate.enums.poleKind import PoleKind as _MPoleKind
from app.dataModel.climate.planning.climatePlan import ResolvedClimateProfile as _MResolvedClimateProfile
from app.dataModel.climate.enums.climateZone import ClimateZoneProfileData as _MClimateZoneProfileData
from app.dataModel.climate.climatePoleBlendDefaults import ClimatePoleBlendDefaults as _MClimatePoleBlendDefaults
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput as _MClimateLocalInput
from app.dataModel.climate.planning.climatePoints import ClimateAnchorPoint as _MClimateAnchorPoint
from app.dataModel.climate.planning.climatePoints import AnchorSource as _MAnchorSource
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateFeaturePolicy as _MClimateFeaturePolicy
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry as _MWorldTerrainRegistry
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry as _MTerrainRegistryEntry
from app.dataModel.terrain.eligibilityRule import EligibilityRule as _MEligibilityRule
from app.dataModel.terrain.enums.eligibilityOp import EligibilityOp as _MEligibilityOp
from app.dataModel.terrain.hillPolicy import HillPolicy as _MHillPolicy
from app.dataModel.terrain.hillShape import HillShape as _MHillShape
from app.dataModel.terrain.enums.terrainFillRole import TerrainFillRole as _MTerrainFillRole
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as _MHydrologyCellRole
from app.dataModel.climate.planning.inputs.climateLocalInput import ProminenceScale as _MProminenceScale
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput as _MTerrainBaseInput
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings as _MSurfaceGridSettings
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput as _MWaterPlacementInput
from app.dataModel.validation.enums.resolutionMode import ResolutionMode as _MResolutionMode
from app.dataModel.hydrology.seas import HydrologySeasPolicy as _MHydrologySeasPolicy
from app.dataModel.hydrology.bands import HydrologyBands as _MHydrologyBands
from app.dataModel.hydrology.shore import HydrologyShoreDefaults as _MHydrologyShoreDefaults
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy as _MHydrologyLakesPolicy
from app.dataModel.hydrology.declaredBasin import DeclaredBasin as _MDeclaredBasin
from app.dataModel.spatial.regionShape import BboxShape as _MBboxShape
from app.dataModel.spatial.regionShape import EdgeNoise as _MEdgeNoise
from app.dataModel.spatial.regionShape import RegionShapeKind as _MRegionShapeKind
from app.dataModel.spatial.regionShape import EllipseShape as _MEllipseShape
from app.dataModel.spatial.regionShape import PolygonShape as _MPolygonShape
from app.dataModel.spatial.regionShape import AnchorRadiusShape as _MAnchorRadiusShape
from app.dataModel.spatial.regionShape import CorridorShape as _MCorridorShape
from app.dataModel.hydrology.enums.basinKind import BasinKind as _MBasinKind
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry as _MWorldMaterialRegistry
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry as _MMaterialRegistryEntry
from app.dataModel.materials.enums.materialCategory import MaterialCategory as _MMaterialCategory
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import WorldEconomyTierRegistry as _MWorldEconomyTierRegistry
from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry as _MEconomyTierEntry
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline as _MDeclaredCoastline
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose as _MCoastlinePurpose
from app.dataModel.hydrology.enums.waterSide import WaterSide as _MWaterSide
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint as _MHydrologyWaypoint
from app.dataModel.hydrology.declaredLake import DeclaredLake as _MDeclaredLake
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterAnchorInput as _MWaterAnchorInput
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype as _MGeographicSubtype
from app.dataModel.topology.worldTopology import WorldTopology as _MWorldTopology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as _MWorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds as _MWorldBounds
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput as _MReliefPlanInput
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy as _MMountainsCategoryPolicy
from app.dataModel.terrainMasks.mountain.enums import MountainKind as _MMountainKind
from app.dataModel.terrainMasks.mountain.specs import MountainFormBySides as _MMountainFormBySides
from app.dataModel.terrainMasks.mountain.specs import StarForm as _MStarForm
from app.dataModel.terrainMasks.mountain.specs import PeakForm as _MPeakForm
from app.dataModel.terrainMasks.mountain.specs import PlateauForm as _MPlateauForm
from app.dataModel.terrain.relief.specs import ReliefSideSpec as _MReliefSideSpec
from app.dataModel.terrain.relief.enums import ReliefSideKind as _MReliefSideKind
from app.dataModel.terrainMasks.mountain.enums import MountainRangeStyle as _MMountainRangeStyle
from app.dataModel.terrainMasks.worldTerrainMasks import RavinesCategoryPolicy as _MRavinesCategoryPolicy
from app.dataModel.terrainMasks.mountain.specs import MountainSpec as _MMountainSpec
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy as _MObjectReliefPickPolicy
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy as _MReliefContextPickPolicy
from app.dataModel.terrain.relief.enums import ReliefPickMode as _MReliefPickMode
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec as _MMountainRangeSpec
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSides as _MMountainRangeSides
from app.dataModel.terrainMasks.mountain.specs import MountainSaddleSpec as _MMountainSaddleSpec
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import MountainAnchorInput as _MMountainAnchorInput
from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput as _MMountainTemplateInput
from app.dataModel.terrain.relief.enums import ReliefContext as _MReliefContext
from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe as _MMountainSideRecipe
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import TerrainMergeEntry as _MTerrainMergeEntry
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput as _MRiverReliefInput
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as _MHydrologyConnectionType
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput as _MHydrologyPlanInput
from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope as _MHydrologyScope
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy as _MHydrologyRiversPolicy
from app.dataModel.hydrology.rivers import RiverTypeClassify as _MRiverTypeClassify
from app.dataModel.hydrology.declaredRiver import DeclaredRiver as _MDeclaredRiver
from app.dataModel.hydrology.enums.riverSystemRole import RiverSystemRole as _MRiverSystemRole
from app.dataModel.hydrology.enums.riverSystemTopology import RiverSystemTopology as _MRiverSystemTopology
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode as _MRiverDeclareMode
from app.dataModel.hydrology.declaredRiver import HydrologyMouth as _MHydrologyMouth
from app.dataModel.hydrology.declaredRiver import DeclaredRiverSegment as _MDeclaredRiverSegment
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyAnchorInput as _MHydrologyAnchorInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput as _MHydrologyFinalInput
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope as _MPlanEnvelope
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan as _MClimateBasePlan
from app.dataModel.planning.identity.planRef import PlanRef as _MPlanRef
from app.dataModel.planning.identity.planKey import PlanKey as _MPlanKey
from app.dataModel.planning.identity.planKey import WorldPlanScope as _MWorldPlanScope
from app.dataModel.planning.identity.planKey import PlanScopeKind as _MPlanScopeKind
from app.dataModel.planning.identity.planKey import RegionPlanScope as _MRegionPlanScope
from app.dataModel.planning.contracts.planContract import PlanContractRegistry as _MPlanContractRegistry
from app.dataModel.planning.contracts.planContract import PlanContractMetadata as _MPlanContractMetadata
from app.dataModel.planning.contracts.planDependency import PlanDependency as _MPlanDependency
from app.dataModel.climate.planning.climatePoints import ClimatePolePoint as _MClimatePolePoint
from app.dataModel.climate.enums.poleSource import PoleSource as _MPoleSource
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic as _MPlanDiagnostic
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError as _MFieldPathError
from app.dataModel.validation.diagnostics.fieldPathError import ReferenceIssueContext as _MReferenceIssueContext
from app.dataModel.validation.diagnostics.fieldPathError import ReferenceIssueReason as _MReferenceIssueReason
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext as _MRuntimeIssueContext
from app.dataModel.spatial.facing import Facing as _MFacing
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition as _MPlanDiagnosticDisposition
from app.dataModel.climate.planning.climatePlan import ClimateLocalPlan as _MClimateLocalPlan
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan as _MTerrainPlan
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord as _MSurfaceGridCoord
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan as _MWaterPlacementPlan
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace as _MCoordinateSpace
from app.dataModel.placement.water import ResolvedWaterPlacement as _MResolvedWaterPlacement
from app.dataModel.placement.result import ResolvedPlacement as _MResolvedPlacement
from app.dataModel.placement.prepared import PreparedPlacement as _MPreparedPlacement
from app.dataModel.placement.intent import PlacementIntent as _MPlacementIntent
from app.dataModel.placement.intent import PlacementIdentity as _MPlacementIdentity
from app.dataModel.placement.common import PlacementMode as _MPlacementMode
from app.dataModel.placement.common import AbsoluteMovement as _MAbsoluteMovement
from app.dataModel.placement.intent import PlacementDependency as _MPlacementDependency
from app.dataModel.placement.common import DependencyRelation as _MDependencyRelation
from app.dataModel.placement.intent import PlacementOverlap as _MPlacementOverlap
from app.dataModel.placement.common import OverlapRelation as _MOverlapRelation
from app.dataModel.placement.intent import PlacementSeparation as _MPlacementSeparation
from app.dataModel.placement.prepared import PlacementCandidate as _MPlacementCandidate
from app.dataModel.placement.prepared import PlacementFootprint as _MPlacementFootprint
from app.dataModel.placement.prepared import CoastlinePlacementFact as _MCoastlinePlacementFact
from app.dataModel.placement.common import WaterPresence as _MWaterPresence
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec as _MBasinSpec
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan as _MReliefPlan
from app.dataModel.terrain.relief.planning.reliefPlan import MountainLayout as _MMountainLayout
from app.dataModel.terrain.relief.planning.reliefPlan import LightReliefPlan as _MLightReliefPlan
from app.dataModel.spatial.grid.coordinateTypes import LightCellRef as _MLightCellRef
from app.dataModel.terrain.relief.planning.reliefPlan import LightMountainCell as _MLightMountainCell
from app.dataModel.terrain.relief.planning.reliefPlan import LightRavineCell as _MLightRavineCell
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan as _MRiverReliefPlan
from app.dataModel.terrain.relief.planning.reliefPlan import RiverBedRecord as _MRiverBedRecord
from app.dataModel.spatial.grid.coordinateTypes import FineXY as _MFineXY
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyRoutesPlan as _MHydrologyRoutesPlan
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology as _MMapCellHydrology
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind as _MHydrologyShoreKind
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink as _MRiverDrainageLink
from app.dataModel.hydrology.waterBody import WaterBody as _MWaterBody
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion as _MPhysicalWaterUnion
from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute as _MRiverRoute
from app.dataModel.hydrology.planning.hydrologyPlan import RiverPathSegment as _MRiverPathSegment
from app.dataModel.hydrology.planning.hydrologyPlan import DeclaredWaterPaint as _MDeclaredWaterPaint
from app.dataModel.hydrology.planning.hydrologyPlan import LakePaint as _MLakePaint
from app.dataModel.hydrology.planning.hydrologyPlan import CoastlinePaint as _MCoastlinePaint
from app.dataModel.hydrology.planning.hydrologyPlan import SegmentRiverPaint as _MSegmentRiverPaint
from app.dataModel.hydrology.planning.hydrologyPlan import IntentRiverPaint as _MIntentRiverPaint
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan as _MHydrologyPlan

from app.dataModel.terrain.relief.bathymetry.floorProfile import SampledFloorProfile as _MSampledFloorProfile, FieldFloorProfile as _MFieldFloorProfile, FloorProfileKind as _MFloorProfileKind
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe as _MNoiseRecipe, PlateRecipe as _MPlateRecipe, PlateNoiseRecipe as _MPlateNoiseRecipe
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as _MDesignedWaterStrategyKind
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy as _MContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy as _MPlateGenerationPolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy as _MFieldCompositionPolicy, FieldCompositionOperator as _MFieldCompositionOperator

# Stable TLV v1 type IDs. Append entries; never infer IDs from runtime discovery.
SURFACE_MANIFEST = CanonicalSchemaManifest(entries=tuple(
    RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind)
    for identity, owner, kind in (
    (1, _MClimateBaseInput, CanonicalTypeKind.RECORD),
    (2, _MGridBBox, CanonicalTypeKind.RECORD),
    (3, _MClimatePoleMode, CanonicalTypeKind.ENUM),
    (4, _MClimatePolePreset, CanonicalTypeKind.ENUM),
    (5, _MWorldClimateZoneRegistry, CanonicalTypeKind.RECORD),
    (6, _MClimateZoneEntry, CanonicalTypeKind.RECORD),
    (7, _MManualPoleInput, CanonicalTypeKind.RECORD),
    (8, _MPoleKind, CanonicalTypeKind.ENUM),
    (9, _MResolvedClimateProfile, CanonicalTypeKind.RECORD),
    (10, _MClimateZoneProfileData, CanonicalTypeKind.RECORD),
    (11, _MClimatePoleBlendDefaults, CanonicalTypeKind.RECORD),
    (12, _MClimateLocalInput, CanonicalTypeKind.RECORD),
    (13, _MClimateAnchorPoint, CanonicalTypeKind.RECORD),
    (14, _MAnchorSource, CanonicalTypeKind.ENUM),
    (15, _MClimateFeaturePolicy, CanonicalTypeKind.RECORD),
    (16, _MWorldTerrainRegistry, CanonicalTypeKind.RECORD),
    (17, _MTerrainRegistryEntry, CanonicalTypeKind.RECORD),
    (18, _MEligibilityRule, CanonicalTypeKind.RECORD),
    (19, _MEligibilityOp, CanonicalTypeKind.ENUM),
    (20, _MHillPolicy, CanonicalTypeKind.RECORD),
    (21, _MHillShape, CanonicalTypeKind.ENUM),
    (22, _MTerrainFillRole, CanonicalTypeKind.ENUM),
    (23, _MHydrologyCellRole, CanonicalTypeKind.ENUM),
    (24, _MProminenceScale, CanonicalTypeKind.ENUM),
    (25, _MTerrainBaseInput, CanonicalTypeKind.RECORD),
    (26, _MSurfaceGridSettings, CanonicalTypeKind.RECORD),
    (27, _MWaterPlacementInput, CanonicalTypeKind.RECORD),
    (28, _MResolutionMode, CanonicalTypeKind.ENUM),
    (29, _MHydrologySeasPolicy, CanonicalTypeKind.RECORD),
    (30, _MHydrologyBands, CanonicalTypeKind.RECORD),
    (31, _MHydrologyShoreDefaults, CanonicalTypeKind.RECORD),
    (32, _MHydrologyLakesPolicy, CanonicalTypeKind.RECORD),
    (33, _MDeclaredBasin, CanonicalTypeKind.RECORD),
    (34, _MBboxShape, CanonicalTypeKind.RECORD),
    (35, _MEdgeNoise, CanonicalTypeKind.RECORD),
    (36, _MRegionShapeKind, CanonicalTypeKind.ENUM),
    (37, _MEllipseShape, CanonicalTypeKind.RECORD),
    (38, _MPolygonShape, CanonicalTypeKind.RECORD),
    (39, _MAnchorRadiusShape, CanonicalTypeKind.RECORD),
    (40, _MCorridorShape, CanonicalTypeKind.RECORD),
    (41, _MBasinKind, CanonicalTypeKind.ENUM),
    (42, _MWorldMaterialRegistry, CanonicalTypeKind.RECORD),
    (43, _MMaterialRegistryEntry, CanonicalTypeKind.RECORD),
    (44, _MMaterialCategory, CanonicalTypeKind.ENUM),
    (45, _MWorldEconomyTierRegistry, CanonicalTypeKind.RECORD),
    (46, _MEconomyTierEntry, CanonicalTypeKind.RECORD),
    (47, _MDeclaredCoastline, CanonicalTypeKind.RECORD),
    (48, _MWaterSide, CanonicalTypeKind.ENUM),
    (49, _MHydrologyWaypoint, CanonicalTypeKind.RECORD),
    (50, _MDeclaredLake, CanonicalTypeKind.RECORD),
    (51, _MWaterAnchorInput, CanonicalTypeKind.RECORD),
    (52, _MGeographicSubtype, CanonicalTypeKind.ENUM),
    (53, _MWorldTopology, CanonicalTypeKind.RECORD),
    (54, _MWorldTopologyMode, CanonicalTypeKind.ENUM),
    (55, _MWorldBounds, CanonicalTypeKind.RECORD),
    (56, _MReliefPlanInput, CanonicalTypeKind.RECORD),
    (57, _MMountainsCategoryPolicy, CanonicalTypeKind.RECORD),
    (58, _MMountainKind, CanonicalTypeKind.ENUM),
    (59, _MMountainFormBySides, CanonicalTypeKind.RECORD),
    (60, _MStarForm, CanonicalTypeKind.RECORD),
    (61, _MPeakForm, CanonicalTypeKind.RECORD),
    (62, _MPlateauForm, CanonicalTypeKind.RECORD),
    (63, _MReliefSideSpec, CanonicalTypeKind.RECORD),
    (64, _MReliefSideKind, CanonicalTypeKind.ENUM),
    (65, _MMountainRangeStyle, CanonicalTypeKind.ENUM),
    (66, _MRavinesCategoryPolicy, CanonicalTypeKind.RECORD),
    (67, _MMountainSpec, CanonicalTypeKind.RECORD),
    (68, _MObjectReliefPickPolicy, CanonicalTypeKind.RECORD),
    (69, _MReliefContextPickPolicy, CanonicalTypeKind.RECORD),
    (70, _MReliefPickMode, CanonicalTypeKind.ENUM),
    (71, _MMountainRangeSpec, CanonicalTypeKind.RECORD),
    (72, _MMountainRangeSides, CanonicalTypeKind.RECORD),
    (73, _MMountainSaddleSpec, CanonicalTypeKind.RECORD),
    (74, _MMountainAnchorInput, CanonicalTypeKind.RECORD),
    (75, _MMountainTemplateInput, CanonicalTypeKind.RECORD),
    (76, _MReliefContext, CanonicalTypeKind.ENUM),
    (77, _MMountainSideRecipe, CanonicalTypeKind.RECORD),
    (78, _MTerrainMergeEntry, CanonicalTypeKind.RECORD),
    (79, _MRiverReliefInput, CanonicalTypeKind.RECORD),
    (80, _MHydrologyConnectionType, CanonicalTypeKind.ENUM),
    (81, _MHydrologyPlanInput, CanonicalTypeKind.RECORD),
    (82, _MHydrologyScope, CanonicalTypeKind.ENUM),
    (83, _MHydrologyRiversPolicy, CanonicalTypeKind.RECORD),
    (84, _MRiverTypeClassify, CanonicalTypeKind.RECORD),
    (85, _MDeclaredRiver, CanonicalTypeKind.RECORD),
    (86, _MRiverSystemRole, CanonicalTypeKind.ENUM),
    (87, _MRiverSystemTopology, CanonicalTypeKind.ENUM),
    (88, _MRiverDeclareMode, CanonicalTypeKind.ENUM),
    (89, _MHydrologyMouth, CanonicalTypeKind.RECORD),
    (90, _MDeclaredRiverSegment, CanonicalTypeKind.RECORD),
    (91, _MHydrologyAnchorInput, CanonicalTypeKind.RECORD),
    (92, _MHydrologyFinalInput, CanonicalTypeKind.RECORD),
    (93, _MPlanEnvelope[_MClimateBasePlan], CanonicalTypeKind.RECORD),
    (94, _MPlanRef, CanonicalTypeKind.RECORD),
    (95, _MPlanKey, CanonicalTypeKind.RECORD),
    (96, _MWorldPlanScope, CanonicalTypeKind.RECORD),
    (97, _MPlanScopeKind, CanonicalTypeKind.ENUM),
    (98, _MRegionPlanScope, CanonicalTypeKind.RECORD),
    (99, _MPlanContractRegistry, CanonicalTypeKind.RECORD),
    (100, _MPlanContractMetadata, CanonicalTypeKind.RECORD),
    (101, _MPlanDependency, CanonicalTypeKind.RECORD),
    (102, _MClimateBasePlan, CanonicalTypeKind.RECORD),
    (103, _MClimatePolePoint, CanonicalTypeKind.RECORD),
    (104, _MPoleSource, CanonicalTypeKind.ENUM),
    (105, _MPlanDiagnostic, CanonicalTypeKind.RECORD),
    (106, _MFieldPathError, CanonicalTypeKind.RECORD),
    (107, _MReferenceIssueContext, CanonicalTypeKind.RECORD),
    (108, _MReferenceIssueReason, CanonicalTypeKind.ENUM),
    (109, _MRuntimeIssueContext, CanonicalTypeKind.RECORD),
    (110, _MFacing, CanonicalTypeKind.ENUM),
    (111, _MPlanDiagnosticDisposition, CanonicalTypeKind.ENUM),
    (112, _MPlanEnvelope[_MClimateLocalPlan], CanonicalTypeKind.RECORD),
    (113, _MClimateLocalPlan, CanonicalTypeKind.RECORD),
    (114, _MPlanEnvelope[_MTerrainPlan], CanonicalTypeKind.RECORD),
    (115, _MTerrainPlan, CanonicalTypeKind.RECORD),
    (116, _MSurfaceGridCoord, CanonicalTypeKind.RECORD),
    (117, _MPlanEnvelope[_MWaterPlacementPlan], CanonicalTypeKind.RECORD),
    (118, _MWaterPlacementPlan, CanonicalTypeKind.RECORD),
    (119, _MCoordinateSpace, CanonicalTypeKind.ENUM),
    (120, _MResolvedWaterPlacement, CanonicalTypeKind.RECORD),
    (121, _MResolvedPlacement, CanonicalTypeKind.RECORD),
    (122, _MPreparedPlacement, CanonicalTypeKind.RECORD),
    (123, _MPlacementIntent, CanonicalTypeKind.RECORD),
    (124, _MPlacementIdentity, CanonicalTypeKind.RECORD),
    (125, _MPlacementMode, CanonicalTypeKind.ENUM),
    (126, _MAbsoluteMovement, CanonicalTypeKind.ENUM),
    (127, _MPlacementDependency, CanonicalTypeKind.RECORD),
    (128, _MDependencyRelation, CanonicalTypeKind.ENUM),
    (129, _MPlacementOverlap, CanonicalTypeKind.RECORD),
    (130, _MOverlapRelation, CanonicalTypeKind.ENUM),
    (131, _MPlacementSeparation, CanonicalTypeKind.RECORD),
    (132, _MPlacementCandidate, CanonicalTypeKind.RECORD),
    (133, _MPlacementFootprint, CanonicalTypeKind.RECORD),
    (134, _MCoastlinePlacementFact, CanonicalTypeKind.RECORD),
    (135, _MWaterPresence, CanonicalTypeKind.ENUM),
    (136, _MBasinSpec, CanonicalTypeKind.RECORD),
    (137, _MPlanEnvelope[_MReliefPlan], CanonicalTypeKind.RECORD),
    (138, _MReliefPlan, CanonicalTypeKind.RECORD),
    (139, _MMountainLayout, CanonicalTypeKind.RECORD),
    (140, _MLightReliefPlan, CanonicalTypeKind.RECORD),
    (141, _MLightCellRef, CanonicalTypeKind.RECORD),
    (142, _MLightMountainCell, CanonicalTypeKind.RECORD),
    (143, _MLightRavineCell, CanonicalTypeKind.RECORD),
    (144, _MPlanEnvelope[_MRiverReliefPlan], CanonicalTypeKind.RECORD),
    (145, _MRiverReliefPlan, CanonicalTypeKind.RECORD),
    (146, _MRiverBedRecord[_MSurfaceGridCoord], CanonicalTypeKind.RECORD),
    (147, _MRiverBedRecord[_MFineXY], CanonicalTypeKind.RECORD),
    (148, _MPlanEnvelope[_MHydrologyRoutesPlan], CanonicalTypeKind.RECORD),
    (149, _MHydrologyRoutesPlan, CanonicalTypeKind.RECORD),
    (150, _MMapCellHydrology, CanonicalTypeKind.RECORD),
    (151, _MHydrologyShoreKind, CanonicalTypeKind.ENUM),
    (152, _MRiverDrainageLink, CanonicalTypeKind.RECORD),
    (153, _MWaterBody, CanonicalTypeKind.RECORD),
    (154, _MPhysicalWaterUnion, CanonicalTypeKind.RECORD),
    (155, _MRiverRoute[_MSurfaceGridCoord], CanonicalTypeKind.RECORD),
    (156, _MRiverPathSegment[_MSurfaceGridCoord], CanonicalTypeKind.RECORD),
    (157, _MRiverRoute[_MFineXY], CanonicalTypeKind.RECORD),
    (158, _MRiverPathSegment[_MFineXY], CanonicalTypeKind.RECORD),
    (159, _MDeclaredWaterPaint, CanonicalTypeKind.RECORD),
    (160, _MLakePaint, CanonicalTypeKind.RECORD),
    (161, _MCoastlinePaint, CanonicalTypeKind.RECORD),
    (162, _MSegmentRiverPaint, CanonicalTypeKind.RECORD),
    (163, _MIntentRiverPaint, CanonicalTypeKind.RECORD),
    (164, _MPlanEnvelope[_MHydrologyPlan], CanonicalTypeKind.RECORD),
    (165, _MHydrologyPlan, CanonicalTypeKind.RECORD),
    (166, _MCoastlinePurpose, CanonicalTypeKind.ENUM),
    (167, _MSampledFloorProfile, CanonicalTypeKind.RECORD),
    (168, _MFieldFloorProfile, CanonicalTypeKind.RECORD),
    (169, _MFloorProfileKind, CanonicalTypeKind.ENUM),
    (170, _MNoiseRecipe, CanonicalTypeKind.RECORD),
    (171, _MPlateRecipe, CanonicalTypeKind.RECORD),
    (172, _MPlateNoiseRecipe, CanonicalTypeKind.RECORD),
    (173, _MDesignedWaterStrategyKind, CanonicalTypeKind.ENUM),
    (174, _MContinentalNoisePolicy, CanonicalTypeKind.RECORD),
    (175, _MPlateGenerationPolicy, CanonicalTypeKind.RECORD),
    (176, _MFieldCompositionPolicy, CanonicalTypeKind.RECORD),
    (177, _MFieldCompositionOperator, CanonicalTypeKind.ENUM),
)))


