"""Process-local parent light cache — WP-PERF-22 (latency, not SoT)."""

from __future__ import annotations

from app.dataModel.worldPack.parentLightTile import ParentLightTile


class ParentLightCache:
    """Process-local cache keyed by ``(world_uid, gx, gy)``.

    Latency only — disk ``world_map.zst`` remains SoT. Prefer sharing one instance
    per process/world via ``Container.parent_light_cache_for`` so bake→refine hits.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, int, int], ParentLightTile] = {}

    def get(self, world_uid: str, gx: int, gy: int) -> ParentLightTile | None:
        return self._by_key.get((world_uid, int(gx), int(gy)))

    def put(self, tile: ParentLightTile) -> None:
        self._by_key[(tile.world_uid, tile.gx, tile.gy)] = tile

    def invalidate(self, world_uid: str, gx: int, gy: int) -> None:
        self._by_key.pop((world_uid, int(gx), int(gy)), None)

    def clear(self) -> None:
        self._by_key.clear()
