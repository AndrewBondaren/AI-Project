"""Typed debug map-render HTTP payloads — single source for read_path / read_mode / levels keys.

``levels`` semantics
--------------------
- pack world tiles: ``{ LEVEL_LIGHT: ascii, LEVEL_HEIGHT: ascii }``
- pack location: ``{ LEVEL_SURFACE: ascii, \"<z>\": ascii }`` where z are FineTerrain
  run *endpoints* (not every meter in a thick band); query ``?z=`` slices arbitrary world-z
- pack wilderness tile: same ``LEVEL_SURFACE`` / z keys from wilderness chunk mosaic
- legacy tiles: ``WorldTileGridRenderer`` surface key ``-1`` plus numeric z strings
- ``indoor`` on pack location payloads is always False (shape-compat with legacy; structures
  live in patches, not location_terrain blobs)
- world grid: ``ascii`` = terrain/hydro mosaic; ``ascii_height`` = ``surface_z`` mosaic (pack)
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
    "wilderness_tile_l2",
    "wilderness_tile_l2_missing",
    "map_cells",
    "map_cells_tiles",
]

LEVEL_SURFACE = "surface"
LEVEL_LIGHT = "light"
LEVEL_HEIGHT = "height"


@dataclass(frozen=True)
class WorldGridPayload:
    ascii: str
    legend: str
    mark_locations: bool
    cell_size_m: int
    read_path: ReadPath
    read_mode: ReadMode
    ascii_height: str = ""
    legend_height: str = ""

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "ascii": self.ascii,
            "legend": self.legend,
            "mark_locations": self.mark_locations,
            "cell_size_m": self.cell_size_m,
            "read_path": self.read_path,
            "read_mode": self.read_mode,
        }
        if self.ascii_height:
            out["ascii_height"] = self.ascii_height
        if self.legend_height:
            out["legend_height"] = self.legend_height
        return out


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


@dataclass(frozen=True)
class WildernessTileGridPayload:
    """L2 wilderness mosaic for one macro-tile (detailed-bake smoke)."""

    tile_gx: int
    tile_gy: int
    legend: str
    cell_size_m: int
    read_path: ReadPath
    read_mode: ReadMode
    levels: dict[str, str] = field(default_factory=dict)
    z_levels: list[object] = field(default_factory=list)
    chunks_listed: int = 0
    chunks_loaded: int = 0
    column_count: int = 0
    wilderness_refine_status: str | None = None
    ascii: str | None = None
    z: int | None = None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "tile_gx": self.tile_gx,
            "tile_gy": self.tile_gy,
            "legend": self.legend,
            "cell_size_m": self.cell_size_m,
            "read_path": self.read_path,
            "read_mode": self.read_mode,
            "chunks_listed": self.chunks_listed,
            "chunks_loaded": self.chunks_loaded,
            "column_count": self.column_count,
            "z_levels": self.z_levels,
            "levels": self.levels,
        }
        if self.wilderness_refine_status is not None:
            out["wilderness_refine_status"] = self.wilderness_refine_status
        if self.ascii is not None:
            out["ascii"] = self.ascii
        if self.z is not None:
            out["z"] = self.z
        return out
