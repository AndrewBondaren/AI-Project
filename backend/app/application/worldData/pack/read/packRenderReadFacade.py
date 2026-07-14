"""Pack I/O for ASCII map render — L0 light tiles + location_terrain blobs."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.application.worldData.pack.read.packMapHelpers import world_tile_size_m
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.db.models.world import World


@dataclass(frozen=True)
class PackTileLightView:
    """One macro-tile light grid from ``world_map.zst``."""

    gx: int
    gy: int
    side: int
    cells: dict[tuple[int, int], WorldMapCellWire]


@dataclass(frozen=True)
class PackWorldMapRenderSource:
    """Pack present. ``tiles`` may be empty when L0 blobs are not written yet."""

    tiles: list[PackTileLightView]
    pins: LocationsIndexWire
    tile_size_m: int


@dataclass(frozen=True)
class LocationTerrainRenderSource:
    location_uid: str
    volume: TerritoryVolume
    chunk: FineTerrainChunkWire


class PackRenderReadFacade:
    """Typed pack loads for debug ASCII render — no MapCell adaptation."""

    def __init__(self, context: PackReadContext) -> None:
        self._ctx = context

    def read_locations_index(self, world: World) -> LocationsIndexWire:
        if not self._ctx.has_pack_for(world):
            return LocationsIndexWire()
        path = self._ctx.reader_for(world).paths.locations_index_path()
        if not path.is_file():
            return LocationsIndexWire()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return LocationsIndexWire.model_validate(raw)

    def try_world_map_source(self, world: World) -> PackWorldMapRenderSource | None:
        """``None`` = no pack on disk; otherwise pins + tiles (possibly empty)."""
        if not self._ctx.has_pack_for(world):
            return None
        reader = self._ctx.reader_for(world)
        tiles: list[PackTileLightView] = []
        for entry in reader.manifest.tiles:
            if not entry.world_map_path:
                continue
            try:
                side, cells = reader.read_world_map_tile(entry.gx, entry.gy)
            except FileNotFoundError:
                continue
            by_xy = {(c.tx, c.ty): c for c in cells}
            tiles.append(
                PackTileLightView(gx=entry.gx, gy=entry.gy, side=side, cells=by_xy),
            )
        return PackWorldMapRenderSource(
            tiles=tiles,
            pins=self.read_locations_index(world),
            tile_size_m=world_tile_size_m(world),
        )

    def has_location_terrain(self, world: World, location_uid: str) -> bool:
        """Manifest ``terrain_path`` and blob file both present."""
        if not self._ctx.has_pack_for(world):
            return False
        reader = self._ctx.reader_for(world)
        entry = reader.manifest.location_entry(location_uid)
        if entry is None or not entry.terrain_path:
            return False
        return reader.paths.location_terrain_path(location_uid).is_file()

    def try_location_terrain(
        self,
        world: World,
        location_uid: str,
    ) -> LocationTerrainRenderSource | None:
        if not self.has_location_terrain(world, location_uid):
            return None
        reader = self._ctx.reader_for(world)
        entry = reader.manifest.location_entry(location_uid)
        if entry is None:
            return None
        chunk = reader.read_location_terrain(location_uid)
        return LocationTerrainRenderSource(
            location_uid=location_uid,
            volume=entry.territory_volume,
            chunk=chunk,
        )

    def location_uids_with_terrain(self, world: World) -> list[str]:
        if not self._ctx.has_pack_for(world):
            return []
        reader = self._ctx.reader_for(world)
        out: list[str] = []
        for entry in reader.manifest.location_terrain_entries:
            if self.has_location_terrain(world, entry.location_uid):
                out.append(entry.location_uid)
        return sorted(out)
