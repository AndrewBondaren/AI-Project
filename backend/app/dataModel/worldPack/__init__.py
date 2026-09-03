"""World Pack wire POJOs — docs/tz_world_pack_storage.md."""

from app.dataModel.worldPack.climateFieldWire import (
    ClimateBakeStatus,
    ClimateFieldWire,
    ClimateSampleWire,
)
from app.dataModel.worldPack.hydrologyMaskWire import HydrologyMaskWire, WorldMapHydrologyRole
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun
from app.dataModel.worldPack.settlementStructureWire import (
    AreaSlotWire,
    AreaStructureWire,
    BuildingShellWire,
    DistrictStructureWire,
    SettlementStructureWire,
    ShellCellWire,
)
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.dataModel.worldPack.layerPriority import LAYER_PRIORITY_ORDER, MapLayerKind
from app.dataModel.worldPack.mergeMapCells import (
    CellContribution,
    LayerSlice,
    MergedCellView,
    merge_layers,
)
from app.dataModel.worldPack.packReadPolicy import PackReadPolicy
from app.dataModel.worldPack.territoryVolume import TerritoryVolume, inside_location_volume
from app.dataModel.worldPack.territoryVolumePolicy import TerritoryVolumePolicy
from app.dataModel.worldPack.paintedRoadEdge import PaintedRoadEdge
from app.dataModel.worldPack.worldSeamCopy import WorldSeamCopy
from app.dataModel.worldPack.worldBounds import WorldBounds
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.dataModel.worldPack.worldMapCellsPerTile import (
    WORLD_MAP_CELLS_PER_TILE,
    WorldMapCellsPerTilePolicy,
    light_m_for,
    resolve_world_map_cells_per_tile,
    resolve_world_map_side,
)
from app.dataModel.worldPack.mapCellSize import MAP_CELL_SIZE_M_DEFAULT
from app.dataModel.worldPack.lightSettlementFootprint import LightSettlementFootprintPolicy
from app.dataModel.worldPack.gradePipelineStages import GradePipelineStages
from app.dataModel.worldPack.packBakeDefaults import (
    PACK_CODEC_VERSION,
    PackBakeDefaults,
    resolve_detailed_grade_stages,
    resolve_light_tile_cap,
)
from app.dataModel.worldPack.packJobUid import FaceGridAxis, PackJobSiteKind, PackJobUid
from app.dataModel.worldPack.packBakeMode import (
    PACK_BAKE_FULL,
    PACK_BAKE_LIGHT,
    PackBakeApiMode,
    PackBakeMode,
)
from app.dataModel.worldPack.detailedBakeScope import (
    DetailedBakeRequest,
    DetailedBakeScopeKind,
    refine_role_for_detailed_scope,
    resolve_detailed_bake_request,
)
from app.dataModel.worldPack.wildernessRefineStatus import (
    wilderness_refine_status_for_counts,
    wilderness_refine_status_without_expected,
)
from app.dataModel.worldPack.lightFineTilePolicy import LightFineTilePolicy
from app.dataModel.worldPack.packCompleteness import (
    PackCompleteness,
    PackCompletenessSnapshot,
)
from app.dataModel.worldPack.packTilePlan import PackTilePlan, PackTilePlanScope, PackTileRef
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.pathHeadingPolicy import PathHeadingPolicy
from app.dataModel.worldPack.worldPackManifest import (
    PACK_WIRE_VERSION,
    ChunkRef,
    ChunkRefineRole,
    LocationTerrainEntry,
    SettlementStructureEntry,
    TileManifestEntry,
    WildernessRefineStatus,
    WorldPackManifest,
)

__all__ = [
    "PACK_WIRE_VERSION",
    "PACK_CODEC_VERSION",
    "MAP_CELL_SIZE_M_DEFAULT",
    "WORLD_MAP_CELLS_PER_TILE",
    "CellContribution",
    "ChunkRef",
    "ChunkRefineRole",
    "ClimateBakeStatus",
    "ClimateFieldWire",
    "ClimateSampleWire",
    "DetailedBakeRequest",
    "DetailedBakeScopeKind",
    "HydrologyMaskWire",
    "WorldMapHydrologyRole",
    "FineTerrainChunkWire",
    "FineTerrainColumnWire",
    "FineTerrainZRun",
    "AreaSlotWire",
    "AreaStructureWire",
    "BuildingShellWire",
    "DistrictStructureWire",
    "SettlementStructureWire",
    "ShellCellWire",
    "SettlementStructureEntry",
    "GradePipelineStages",
    "LAYER_PRIORITY_ORDER",
    "LayerSlice",
    "LocationTerrainEntry",
    "LocationsIndexPin",
    "LocationsIndexWire",
    "MapLayerKind",
    "MergedCellView",
    "LightFineTilePolicy",
    "PACK_BAKE_FULL",
    "PACK_BAKE_LIGHT",
    "PackBakeApiMode",
    "PackBakeDefaults",
    "PackBakeMode",
    "PackJobSiteKind",
    "PackJobUid",
    "PaintedRoadEdge",
    "FaceGridAxis",
    "PackCompleteness",
    "PackCompletenessSnapshot",
    "PackTilePlan",
    "PackTilePlanScope",
    "PackTileRef",
    "PathHeadingPolicy",
    "PackReadPolicy",
    "TerritoryVolume",
    "TerritoryVolumePolicy",
    "TileManifestEntry",
    "WildernessRefineStatus",
    "WorldSeamCopy",
    "WorldBounds",
    "WorldMapCellWire",
    "WorldMapCellsPerTilePolicy",
    "LightSettlementFootprintPolicy",
    "ParentLightTile",
    "ParentLightRefinePolicy",
    "WorldPackManifest",
    "inside_location_volume",
    "light_m_for",
    "merge_layers",
    "refine_role_for_detailed_scope",
    "resolve_detailed_bake_request",
    "resolve_detailed_grade_stages",
    "resolve_light_tile_cap",
    "resolve_world_map_cells_per_tile",
    "resolve_world_map_side",
    "wilderness_refine_status_for_counts",
    "wilderness_refine_status_without_expected",
]
