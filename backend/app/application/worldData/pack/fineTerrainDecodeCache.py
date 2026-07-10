"""LRU cache for decoded wilderness chunks and location terrain blobs — MERGE-8."""

from __future__ import annotations

from collections import OrderedDict
from typing import Callable, TypeVar

from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire
from app.dataModel.worldPack.packReadPolicy import PackReadPolicy

T = TypeVar("T")

WildernessChunkKey = tuple[int, int, int, int]


class FineTerrainDecodeCache:
    def __init__(self, policy: PackReadPolicy | None = None) -> None:
        resolved = policy or PackReadPolicy.canonical_defaults()
        self._chunk_cap = resolved.wilderness_chunk_lru_capacity
        self._location_cap = resolved.location_terrain_lru_capacity
        self._chunks: OrderedDict[WildernessChunkKey, FineTerrainChunkWire] = OrderedDict()
        self._locations: OrderedDict[str, FineTerrainChunkWire] = OrderedDict()

    def get_wilderness_chunk(
        self,
        key: WildernessChunkKey,
        loader: Callable[[], FineTerrainChunkWire],
    ) -> FineTerrainChunkWire:
        return self._get(self._chunks, key, self._chunk_cap, loader)

    def get_location_terrain(
        self,
        location_uid: str,
        loader: Callable[[], FineTerrainChunkWire],
    ) -> FineTerrainChunkWire:
        return self._get(self._locations, location_uid, self._location_cap, loader)

    @staticmethod
    def _get(
        store: OrderedDict,
        key,
        capacity: int,
        loader: Callable[[], T],
    ) -> T:
        if key in store:
            store.move_to_end(key)
            return store[key]
        value = loader()
        store[key] = value
        if len(store) > capacity:
            store.popitem(last=False)
        return value

    def wilderness_chunk_count(self) -> int:
        return len(self._chunks)

    def location_terrain_count(self) -> int:
        return len(self._locations)
