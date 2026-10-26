"""map_cell_patches.layer_kind wire — docs/tz_world_pack_storage.md § Patch Store."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class MapCellPatchLayerKind(StrEnum):
    STRUCTURE = "structure"
    SETTLEMENT = "settlement"
    TERRAIN_DELTA = "terrain_delta"
    CLIMATE_DELTA = "climate_delta"
    ORE = "ore"
    CAVE = "cave"

    @classmethod
    def from_wire(cls, value: str | MapCellPatchLayerKind | None) -> MapCellPatchLayerKind:
        if value is None:
            return cls.STRUCTURE
        if isinstance(value, cls):
            return value
        norm = str(value).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return cls.STRUCTURE


class MapCellPatchLayerPolicy(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-MAP-CELL-PATCH-LAYER-POLICY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    default_kind: MapCellPatchLayerKind = MapCellPatchLayerKind.STRUCTURE

    @classmethod
    def canonical_defaults(cls) -> MapCellPatchLayerPolicy:
        return cls()
