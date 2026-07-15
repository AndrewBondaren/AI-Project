"""Typed parent L0 world_map tile view — WP-PERF-22 / Parent light SoT."""

from __future__ import annotations

from types import MappingProxyType
from typing import ClassVar, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.dataModel.worldPack.worldMapCellsPerTile import WORLD_MAP_CELLS_PER_TILE


class ParentLightTile(BaseModel):
    """Immutable L0 wire view for one macro-tile — refine input (not live compose)."""

    SCHEMA_ID: ClassVar[str] = "SCH-PARENT-LIGHT-TILE"

    model_config = ConfigDict(extra="ignore", frozen=True, arbitrary_types_allowed=True)

    world_uid: str
    gx: int
    gy: int
    side: int = Field(default=WORLD_MAP_CELLS_PER_TILE, ge=1)
    tile_m: int = Field(ge=1)
    # (tx, ty) → wire cell; MappingProxyType after from_cells
    cells: Mapping[tuple[int, int], WorldMapCellWire] = Field(default_factory=dict)

    @classmethod
    def from_cells(
        cls,
        *,
        world_uid: str,
        gx: int,
        gy: int,
        side: int,
        tile_m: int,
        cells: list[WorldMapCellWire],
    ) -> ParentLightTile:
        by_xy: dict[tuple[int, int], WorldMapCellWire] = {
            (int(c.tx), int(c.ty)): c for c in cells
        }
        return cls(
            world_uid=world_uid,
            gx=int(gx),
            gy=int(gy),
            side=max(1, int(side)),
            tile_m=max(1, int(tile_m)),
            cells=MappingProxyType(by_xy),
        )

    @property
    def light_m(self) -> int:
        return max(1, self.tile_m // self.side)

    def cell_at(self, tx: int, ty: int) -> WorldMapCellWire | None:
        return self.cells.get((int(tx), int(ty)))

    def meters_to_tx_ty(self, xm: int, ym: int) -> tuple[int, int]:
        """Macro-local meters → light (tx, ty) clamped to tile."""
        origin_x = self.gx * self.tile_m
        origin_y = self.gy * self.tile_m
        lx = int(xm) - origin_x
        ly = int(ym) - origin_y
        lm = self.light_m
        tx = min(self.side - 1, max(0, lx // lm))
        ty = min(self.side - 1, max(0, ly // lm))
        return tx, ty

    def surface_z_at(self, tx: int, ty: int) -> int:
        cell = self.cell_at(tx, ty)
        if cell is None:
            raise LookupError(
                f"parent light missing cell ({tx},{ty}) on tile ({self.gx},{self.gy})",
            )
        return int(cell.surface_z)
