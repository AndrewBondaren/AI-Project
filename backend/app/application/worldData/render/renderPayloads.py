"""Typed debug map-render HTTP payloads — single source for read_path / read_mode / levels keys.

``levels`` semantics
--------------------
- pack world tiles: ``{ LEVEL_LIGHT: ascii }``
- pack location: ``{ LEVEL_SURFACE: ascii, \"<z>\": ascii }`` where z are FineTerrain
  run *endpoints* (not every meter in a thick band); query ``?z=`` slices arbitrary world-z
- legacy tiles: ``WorldTileGridRenderer`` surface key ``-1`` plus numeric z strings
- ``indoor`` on pack location payloads is always False (shape-compat with legacy; structures
  live in patches, not location_terrain blobs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ReadPath = Literal["pack", "legacy"]
ReadMode = Literal[
    "world_map_light",
    "world_map_light_mask",
    "world_map_light_macro_aggregate",
    "location_terrain",
    "location_terrain_missing",
    "map_cells",
    "map_cells_tiles",
]

LEVEL_SURFACE = "surface"
LEVEL_LIGHT = "light"


@dataclass(frozen=True)
class WorldGridPayload:
    ascii: str
    legend: str
    mark_locations: bool
    cell_size_m: int
    read_path: ReadPath
    read_mode: ReadMode

    def to_dict(self) -> dict[str, object]:
        return {
            "ascii": self.ascii,
            "legend": self.legend,
            "mark_locations": self.mark_locations,
            "cell_size_m": self.cell_size_m,
            "read_path": self.read_path,
            "read_mode": self.read_mode,
        }


@dataclass(frozen=True)
class WorldTileEntryPayload:
    tile_gx: int
    tile_gy: int
    levels: dict[str, str]
    z_levels: list[object]
    legend: str
    grid_kind: str | None = None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "tile_gx": self.tile_gx,
            "tile_gy": self.tile_gy,
            "z_levels": self.z_levels,
            "levels": self.levels,
            "legend": self.legend,
        }
        if self.grid_kind is not None:
            out["grid_kind"] = self.grid_kind
        return out


@dataclass(frozen=True)
class WorldTileGridsPayload:
    world_uid: str
    cell_size_m: int
    tiles: dict[str, WorldTileEntryPayload]
    read_path: ReadPath
    read_mode: ReadMode

    def to_dict(self) -> dict[str, object]:
        return {
            "world_uid": self.world_uid,
            "cell_size_m": self.cell_size_m,
            "tile_keys": list(self.tiles.keys()),
            "tiles": {k: v.to_dict() for k, v in self.tiles.items()},
            "read_path": self.read_path,
            "read_mode": self.read_mode,
        }


@dataclass(frozen=True)
class LocationEntryPayload:
    indoor: bool
    levels: dict[str, str]
    z_levels: list[object]
    legend: str
    read_mode: ReadMode | None = None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "indoor": self.indoor,
            "z_levels": self.z_levels,
            "levels": self.levels,
            "legend": self.legend,
        }
        if self.read_mode is not None:
            out["read_mode"] = self.read_mode
        return out


@dataclass(frozen=True)
class LocationGridsPayload:
    world_uid: str
    cell_size_m: int
    location_uids: list[str]
    locations: dict[str, LocationEntryPayload]
    outdoor_legend: str
    read_path: ReadPath
    read_mode: ReadMode
    locations_index_pins: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "world_uid": self.world_uid,
            "cell_size_m": self.cell_size_m,
            "location_uids": self.location_uids,
            "locations": {k: v.to_dict() for k, v in self.locations.items()},
            "outdoor_legend": self.outdoor_legend,
            "read_path": self.read_path,
            "read_mode": self.read_mode,
        }
        if self.locations_index_pins:
            out["locations_index_pins"] = self.locations_index_pins
        return out


@dataclass(frozen=True)
class LocationGridPayload:
    legend: str
    cell_size_m: int
    read_path: ReadPath
    read_mode: ReadMode
    indoor: bool = False
    levels: dict[str, str] | None = None
    ascii: str | None = None
    z: int | None = None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "legend": self.legend,
            "cell_size_m": self.cell_size_m,
            "read_path": self.read_path,
            "read_mode": self.read_mode,
        }
        if self.ascii is not None:
            out["ascii"] = self.ascii
        if self.z is not None:
            out["z"] = self.z
        if self.levels is not None:
            out["levels"] = self.levels
            out["indoor"] = self.indoor
        return out
