"""World Pack wire POJOs — docs/tz_world_pack_storage.md."""

from app.dataModel.worldPack.wire.climateFieldWire import (
    ClimateBakeStatus,
    ClimateFieldWire,
    ClimateSampleWire,
)
from app.dataModel.worldPack.wire.hydrologyMaskWire import HydrologyMaskWire, WorldMapHydrologyRole
from app.dataModel.worldPack.wire.fineTerrainChunkWire import FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun
from app.dataModel.worldPack.wire.settlementStructureWire import (
    AreaSlotWire,
    AreaStructureWire,
    BuildingShellWire,
    DistrictStructureWire,
    SettlementStructureWire,
    ShellCellWire,
)
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.dataModel.worldPack.bake.layerPriority import LAYER_PRIORITY_ORDER, MapLayerKind
from app.dataModel.worldPack.wire.mergeMapCells import (
    CellContribution,
    LayerSlice,
    MergedCellView,
    merge_layers,
)
from app.dataModel.worldPack.bake.packReadPolicy import PackReadPolicy
from app.dataModel.worldPack.wire.territoryVolume import (
    TerritoryVolume,
    empty_inclusive,
    inside_location_volume,
    volumes_conflict,
)
from app.dataModel.worldPack.wire.territoryVolumePolicy import TerritoryVolumePolicy
from app.dataModel.worldPack.wire.paintedRoadEdge import PaintedRoadEdge
from app.dataModel.worldPack.wire.worldSeamCopy import WorldSeamCopy
from app.dataModel.worldPack.wire.worldBounds import WorldBounds
from app.dataModel.worldPack.wire.worldMapCellWire import WorldMapCellWire
from app.dataModel.worldPack.wire.worldMapCellsPerTile import (
    WORLD_MAP_CELLS_PER_TILE,
    WorldMapCellsPerTilePolicy,
    light_m_for,
    resolve_world_map_cells_per_tile,
    resolve_world_map_side,
)
from app.dataModel.worldPack.wire.mapCellSize import FINE_CELLS_PER_MAP_CELL_DEFAULT
from app.dataModel.worldPack.wire.lightSettlementFootprint import LightSettlementFootprintPolicy
from app.dataModel.worldPack.bake.gradePipelineStages import GradePipelineStages
from app.dataModel.worldPack.bake.packBakeDefaults import (
    PACK_CODEC_VERSION,
    PackBakeDefaults,
    resolve_detailed_grade_stages,
    resolve_light_tile_cap,
)
from app.dataModel.worldPack.bake.packJobUid import FaceGridAxis, PackJobSiteKind, PackJobUid
from app.dataModel.worldPack.bake.packBakeMode import (
    PACK_BAKE_FULL,
    PACK_BAKE_LIGHT,
    PackBakeApiMode,
    PackBakeMode,
)
from app.dataModel.worldPack.bake.detailedBakeScope import (
    DetailedBakeRequest,
    DetailedBakeScopeKind,
    refine_role_for_detailed_scope,
    resolve_detailed_bake_request,
)
from app.dataModel.worldPack.bake.wildernessRefineStatus import (
    wilderness_refine_status_for_counts,
    wilderness_refine_status_without_expected,
)
from app.dataModel.worldPack.wire.settlementStructureStatus import settlement_structure_status_for
from app.dataModel.worldPack.bake.lightFineTilePolicy import LightFineTilePolicy
from app.dataModel.worldPack.bake.packCompleteness import (
    PackCompleteness,
    PackCompletenessSnapshot,
)
from app.dataModel.worldPack.bake.packTilePlan import PackTilePlan, PackTilePlanScope, PackTileRef
from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.bake.pathHeadingPolicy import PathHeadingPolicy
from app.dataModel.worldPack.meta.worldPackManifest import (
    PACK_WIRE_VERSION,
    ChunkRef,
    ChunkRefineRole,
    LocationTerrainEntry,
    SettlementStructureEntry,
    SettlementStructureStatus,
    TileManifestEntry,
    WildernessRefineStatus,
    WorldPackManifest,
)

__all__ = [
    "PACK_WIRE_VERSION",
    "PACK_CODEC_VERSION",
    "FINE_CELLS_PER_MAP_CELL_DEFAULT",
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
    "SettlementStructureStatus",
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
    "empty_inclusive",
    "volumes_conflict",
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
    "settlement_structure_status_for",
    "wilderness_refine_status_for_counts",
    "wilderness_refine_status_without_expected",
]
