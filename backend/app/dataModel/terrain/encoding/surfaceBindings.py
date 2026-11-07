"""Stable surface TLV registrations for app.dataModel.terrain."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.enums.eligibilityOp import EligibilityOp
from app.dataModel.terrain.enums.terrainFillRole import TerrainFillRole
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.hillShape import HillShape
from app.dataModel.terrain.hills.acceptedHill import AcceptedHill, HillLayout
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterAnchorInput, WaterPlacementInput
from app.dataModel.terrain.planning.natural.preparedTerrain import NaturalTerrainTile, PreparedNaturalTerrain
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.waterPlacementPlan import GeoWaterPlacementPlan, WaterPlacementPlan
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.regions.regionPlanningInput import RegionGeometryInput, TerrainRegionPlanningInput
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan, TerrainRegionsSnapshot
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.terrain.terrainCategoryEntry import TerrainCategoryEntry
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainCategoryRegistry import WorldTerrainCategoryRegistry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (16, WorldTerrainRegistry, CanonicalTypeKind.RECORD),
    (17, TerrainRegistryEntry, CanonicalTypeKind.RECORD),
    (18, EligibilityRule, CanonicalTypeKind.RECORD),
    (19, EligibilityOp, CanonicalTypeKind.ENUM),
    (20, HillPolicy, CanonicalTypeKind.RECORD),
    (21, HillShape, CanonicalTypeKind.ENUM),
    (22, TerrainFillRole, CanonicalTypeKind.ENUM),
    (25, TerrainBaseInput, CanonicalTypeKind.RECORD),
    (27, WaterPlacementInput, CanonicalTypeKind.RECORD),
    (51, WaterAnchorInput, CanonicalTypeKind.RECORD),
    (114, PlanEnvelope[TerrainPlan], CanonicalTypeKind.RECORD),
    (115, TerrainPlan, CanonicalTypeKind.RECORD),
    (117, PlanEnvelope[WaterPlacementPlan], CanonicalTypeKind.RECORD),
    (118, WaterPlacementPlan, CanonicalTypeKind.RECORD),
    (236, TerrainRegionPlanningInput, CanonicalTypeKind.RECORD),
    (237, RegionGeometryInput, CanonicalTypeKind.RECORD),
    (238, RegionCoverage, CanonicalTypeKind.RECORD),
    (239, CoverageSpan, CanonicalTypeKind.RECORD),
    (240, GeoWaterPlacementInput, CanonicalTypeKind.RECORD),
    (253, WorldTerrainCategoryRegistry, CanonicalTypeKind.RECORD),
    (254, TerrainCategoryEntry, CanonicalTypeKind.RECORD),
    (256, PlanEnvelope[TerrainRegionPlan], CanonicalTypeKind.RECORD),
    (257, TerrainRegionPlan, CanonicalTypeKind.RECORD),
    (258, TerrainRegionsSnapshot, CanonicalTypeKind.RECORD),
    (259, TerrainRegionExtent, CanonicalTypeKind.RECORD),
    (260, PlanEnvelope[GeoWaterPlacementPlan], CanonicalTypeKind.RECORD),
    (261, GeoWaterPlacementPlan, CanonicalTypeKind.RECORD),
    (283, FineSurfaceWindow, CanonicalTypeKind.RECORD),
    (284, PlanEnvelope[FineSurfaceWindow], CanonicalTypeKind.RECORD),
    (292, AcceptedHill, CanonicalTypeKind.RECORD),
    (293, HillLayout, CanonicalTypeKind.RECORD),
    (294, NaturalTerrainTile, CanonicalTypeKind.RECORD),
    (295, PreparedNaturalTerrain, CanonicalTypeKind.RECORD),
    (296, PlanEnvelope[PreparedNaturalTerrain], CanonicalTypeKind.RECORD),
)
