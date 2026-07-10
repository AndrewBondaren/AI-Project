"""LRU cache for decoded L2 wilderness chunks and location blobs — MERGE-8."""

from __future__ import annotations

from collections import OrderedDict
from typing import Callable, TypeVar

from app.dataModel.worldPack.l2ChunkWire import L2ChunkWire
from app.dataModel.worldPack.packReadPolicy import PackReadPolicy

T = TypeVar("T")

WildernessChunkKey = tuple[int, int, int, int]


class PackL2DecodeCache:
    def __init__(self, policy: PackReadPolicy | None = None) -> None:
        resolved = policy or PackReadPolicy.canonical_defaults()
        self._chunk_cap = resolved.l2_chunk_lru_capacity
        self._location_cap = resolved.location_l2_lru_capacity
        self._chunks: OrderedDict[WildernessChunkKey, L2ChunkWire] = OrderedDict()
        self._locations: OrderedDict[str, L2ChunkWire] = OrderedDict()

    def get_wilderness_chunk(
        self,
        key: WildernessChunkKey,
        loader: Callable[[], L2ChunkWire],
    ) -> L2ChunkWire:
        return self._get(self._chunks, key, self._chunk_cap, loader)

    def get_location_l2(
        self,
        location_uid: str,
        loader: Callable[[], L2ChunkWire],
    ) -> L2ChunkWire:
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

    def location_l2_count(self) -> int:
        return len(self._locations)
