"""Live terrain keys over immutable pack membership, below WP-20 patches."""

from collections.abc import Mapping, Sequence

from pydantic import TypeAdapter

from app.application.jsonValidation import terrain_masks
from app.application.worldData.regions.regionStateLog import log_overlap_rerank_deferred
from app.application.worldData.regions.regionStateMapping import state_from_row
from app.dataModel.regions.regionState import RegionState
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.worldPack.bake.layerPriority import MapLayerKind
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from app.dataModel.worldPack.wire.mergeMapCells import LayerSlice, MergedCellView, merge_layers
from app.db.models.world import World
from app.db.repositories.iRegionStateRepository import IRegionStateRepository

_terrain_key = TypeAdapter(TerrainKey)
type CellLayers = dict[tuple[int, int, int], list[LayerSlice]]


def overlay_terrain(baked: TerrainKey, region_uid: str | None,
                    states: Mapping[str, RegionState], fallback: TerrainKey) -> TerrainKey:
    """Only the terrain key changes; no geometry, role, material or state writes."""
    state = states.get(region_uid) if region_uid is not None else None
    if state is None:
        return baked
    if state.tombstone:
        return fallback
    return state.current_type if state.current_type != baked else baked


class RegionStateOverlay:
    def __init__(self, repo: IRegionStateRepository | None = None) -> None:
        self._repo = repo

    async def merge(self, world: World, cells: CellLayers,
                    entries: Sequence[WildernessRegionEntry]) -> list[MergedCellView]:
        """One batch snapshot per read, one overlay point for all pack layers."""
        uids = sorted({layer.cell.region_uid for layers in cells.values() for layer in layers
                       if layer.kind != MapLayerKind.PATCH and layer.cell is not None
                       and layer.cell.region_uid is not None})
        states: dict[str, RegionState] = {}
        if self._repo is not None and uids:
            for row in await self._repo.get_many(world.world_uid, uids):
                if row.world_uid != world.world_uid:
                    raise ValueError("region state overlay contains another world")
                state = state_from_row(row)
                states[state.region_uid] = state
        if not states:
            return [merge_layers(x, y, z, layers) for (x, y, z), layers in cells.items()]
        # Transitional policy interface until the 10b landcover cutover.
        fallback = _terrain_key.validate_python(terrain_masks(world).default_landcover.fallback_terrain)
        changed: set[str] = set()
        result = []
        for (x, y, z), layers in cells.items():
            resolved = []
            for layer in layers:
                cell = layer.cell
                if (layer.kind != MapLayerKind.PATCH and cell is not None
                        and cell.region_uid in states and cell.system_terrain is not None):
                    baked = _terrain_key.validate_python(cell.system_terrain)
                    key = overlay_terrain(baked, cell.region_uid, states, fallback)
                    if key != baked:
                        changed.add(cell.region_uid)
                        layer = layer.model_copy(update={
                            "cell": cell.model_copy(update={"system_terrain": key}),
                        })
                resolved.append(layer)
            result.append(merge_layers(x, y, z, resolved))
        self._log_overlaps(world.world_uid, changed, states, entries)
        return result

    @staticmethod
    def _log_overlaps(world_uid: str, changed: set[str], states: Mapping[str, RegionState],
                      entries: Sequence[WildernessRegionEntry]) -> None:
        by_uid = {entry.region_uid: entry for entry in entries}
        for uid in sorted(changed):
            entry = by_uid.get(uid)
            if entry is None or states[uid].tombstone or states[uid].current_type == entry.current_type:
                continue
            bbox = entry.bbox
            neighbors = sorted(other.region_uid for other in entries
                               if other.region_uid != uid
                               and bbox.x_min <= other.bbox.x_max and bbox.x_max >= other.bbox.x_min
                               and bbox.y_min <= other.bbox.y_max and bbox.y_max >= other.bbox.y_min)
            if neighbors:
                log_overlap_rerank_deferred(world_uid, uid, neighbors)
