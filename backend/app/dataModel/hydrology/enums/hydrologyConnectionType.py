"""Wire `connection_type` keys for hydrology declare — ENUM-E E-10, tz_terrain_hydrology.md.

Subset of ``WorldConnectionTypeRegistry`` — keys listed in
``HYDROLOGY_CONNECTION_TYPE_KEYS``, values resolved via ``require_engine``.
"""

from __future__ import annotations

from enum import StrEnum

from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    HYDROLOGY_CONNECTION_TYPE_KEYS,
    WorldConnectionTypeRegistry,
)


class HydrologyConnectionType(StrEnum):
    LAKE_SHORELINE = WorldConnectionTypeRegistry.require_engine("lake_shoreline")
    COASTLINE = WorldConnectionTypeRegistry.require_engine("coastline")
    RIVER = WorldConnectionTypeRegistry.require_engine("river")
    MOUNTAIN_RIVER = WorldConnectionTypeRegistry.require_engine("mountain_river")

    @classmethod
    def from_wire(cls, key: str | HydrologyConnectionType | None) -> HydrologyConnectionType | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return None


if frozenset(member.value for member in HydrologyConnectionType) != frozenset(
    HYDROLOGY_CONNECTION_TYPE_KEYS
):
    raise RuntimeError(
        "HydrologyConnectionType members must match HYDROLOGY_CONNECTION_TYPE_KEYS",
    )
