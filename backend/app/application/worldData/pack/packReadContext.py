"""Shared pack reader cache and presence — REVIEW-5."""

from __future__ import annotations

from app.dataModel.worldPack.packReadPolicy import PackReadPolicy
from app.application.worldData.pack.packL2DecodeCache import PackL2DecodeCache
from app.application.worldData.pack.packPresence import has_pack as resolve_has_pack
from app.application.worldData.pack.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.worldPackReader import WorldPackReader
from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire
from app.db.models.world import World


class PackReadContext:
    """Per-world_uid pack paths, reader cache, coarse climate decode."""

    def __init__(
        self,
        world_uid: str,
        *,
        db_path: str,
        read_policy: PackReadPolicy | None = None,
    ) -> None:
        self.world_uid = world_uid
        self._db_path = db_path
        self._default_paths = WorldPackPaths.from_db_parent(db_path, world_uid)
        self._readers: dict[str, WorldPackReader] = {}
        self._climate_cache: dict[str, ClimateFieldWire | None] = {}
        self._l2_cache = PackL2DecodeCache(read_policy)

    def paths_for(self, world: World) -> WorldPackPaths:
        return WorldPackPaths.for_world(world, self._db_path)

    def reader_for(self, world: World) -> WorldPackReader:
        paths = self.paths_for(world)
        key = str(paths.root)
        reader = self._readers.get(key)
        if reader is None:
            reader = WorldPackReader(paths, l2_cache=self._l2_cache)
            self._readers[key] = reader
        return reader

    @property
    def l2_decode_cache(self) -> PackL2DecodeCache:
        return self._l2_cache

    def has_pack(self) -> bool:
        return resolve_has_pack(None, self._default_paths, db_path=self._db_path)

    def has_pack_for(self, world: World) -> bool:
        return resolve_has_pack(world, self._default_paths, db_path=self._db_path)

    def climate_field(self, world: World) -> ClimateFieldWire | None:
        key = str(self.paths_for(world).root)
        if key not in self._climate_cache:
            try:
                self._climate_cache[key] = self.reader_for(world).read_climate_coarse()
            except FileNotFoundError:
                self._climate_cache[key] = None
        return self._climate_cache[key]
