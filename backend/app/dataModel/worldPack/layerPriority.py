"""Layer priority for pack read merge — WP-20."""

from __future__ import annotations

from enum import IntEnum


class MapLayerKind(IntEnum):
    """Lower value = higher priority at read merge."""

    PATCH = 0
    PLAYER_SCENE = 1
    PLAYER_PATH = 2
    LOCATION = 3
    WILDERNESS = 4
    L0 = 5


LAYER_PRIORITY_ORDER: tuple[MapLayerKind, ...] = (
    MapLayerKind.PATCH,
    MapLayerKind.PLAYER_SCENE,
    MapLayerKind.PLAYER_PATH,
    MapLayerKind.LOCATION,
    MapLayerKind.WILDERNESS,
    MapLayerKind.L0,
)
