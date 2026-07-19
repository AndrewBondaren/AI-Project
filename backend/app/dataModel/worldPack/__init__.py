"""World Pack wire POJOs — docs/tz_world_pack_storage.md."""

from app.dataModel.worldPack.climateFieldWire import (
    ClimateBakeStatus,
    ClimateFieldWire,
    ClimateSampleWire,
)
from app.dataModel.worldPack.hydrologyMaskWire import HydrologyMaskWire, WorldMapHydrologyRole
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun
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
from app.dataModel.worldPack.worldBounds import WorldBounds
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.dataModel.worldPack.worldMapCellsPerTile import (
    WORLD_MAP_CELLS_PER_TILE,
    WorldMapCellsPerTilePolicy,
    light_m_for,
    resolve_world_map_cells_per_tile,
    resolve_world_map_side,
)
from app.dataModel.worldPack.lightSettlementFootprint import LightSettlementFootprintPolicy
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults, resolve_light_tile_cap
from app.dataModel.worldPack.packBakeMode import PackBakeApiMode, PackBakeMode
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
    LocationTerrainEntry,
    TileManifestEntry,
    WorldPackManifest,
)

__all__ = [
    "PACK_WIRE_VERSION",
    "WORLD_MAP_CELLS_PER_TILE",
    "CellContribution",
    "ChunkRef",
    "ClimateBakeStatus",
    "ClimateFieldWire",
    "ClimateSampleWire",
    "HydrologyMaskWire",
    "WorldMapHydrologyRole",
    "FineTerrainChunkWire",
    "FineTerrainColumnWire",
    "FineTerrainZRun",
    "LAYER_PRIORITY_ORDER",
    "LayerSlice",
    "LocationTerrainEntry",
    "LocationsIndexPin",
    "LocationsIndexWire",
    "MapLayerKind",
    "MergedCellView",
    "LightFineTilePolicy",
    "PackBakeApiMode",
    "PackBakeDefaults",
    "PackBakeMode",
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
    "resolve_light_tile_cap",
    "resolve_world_map_cells_per_tile",
    "resolve_world_map_side",
]
