"""Pack-native L0 ASCII — ``WorldMapCellWire`` + ``locations_index`` (no MapCell round-trip)."""

from __future__ import annotations

from app.application.worldData.pack.read.packMapHelpers import (
    tile_index,
    world_map_sample_index,
)
from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.gridAxes import format_grid_header
from app.application.worldData.render.mapSymbols import (
    LOCATION_PIN_SYMBOL,
    render_map_legend,
    symbol_for_role_or_terrain,
)
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


def wire_symbol(cell: WorldMapCellWire, *, mark_pin: bool = False) -> str:
    if mark_pin and cell.location_pin is not None:
        return LOCATION_PIN_SYMBOL
    role_name: str | None = None
    if cell.hydrology_role != WorldMapHydrologyRole.NONE:
        fine = cell.hydrology_role.to_fine_role()
        role_name = fine.value if fine is not None else cell.hydrology_role.name.lower()
    return symbol_for_role_or_terrain(
        hydrology_role=role_name,
        system_terrain=cell.system_terrain,
    )


def _pin_macro(pin: LocationsIndexPin, tile_size_m: int) -> tuple[int, int]:
    gx, _ = tile_index(pin.map_x, tile_size_m)
    gy, _ = tile_index(pin.map_y, tile_size_m)
    return gx, gy


def _pin_light_xy(
    pin: LocationsIndexPin,
    tile: PackTileLightView,
    tile_size_m: int,
) -> tuple[int, int] | None:
    gx, lx = tile_index(pin.map_x, tile_size_m)
    gy, ly = tile_index(pin.map_y, tile_size_m)
    if gx != tile.gx or gy != tile.gy or tile.side <= 0:
        return None
    return (
        world_map_sample_index(lx, tile_size_m, tile.side),
        world_map_sample_index(ly, tile_size_m, tile.side),
    )


class WorldMapPackRenderer:
    """L0 world map ASCII from pack light tiles + optional locations_index pins."""

    def __init__(
        self,
        tiles: list[PackTileLightView],
        *,
        tile_size_m: int,
        pins: LocationsIndexWire | None = None,
    ) -> None:
        self._tile_m = max(1, int(tile_size_m))
        self._by_xy: dict[tuple[int, int], PackTileLightView] = {
            (t.gx, t.gy): t for t in tiles
        }
        self._pins = list(pins.locations) if pins is not None else []
        self._pin_macros = {_pin_macro(p, self._tile_m) for p in self._pins}

    def _rep_cell(self, tile: PackTileLightView) -> WorldMapCellWire | None:
        """Overview aggregate only — NOT L0 mask SoT (use render_tile_light_grid)."""
        if not tile.cells:
            return None
        mid = max(0, tile.side // 2)
        if (mid, mid) in tile.cells:
            return tile.cells[(mid, mid)]
        for cell in tile.cells.values():
            if cell.hydrology_role != WorldMapHydrologyRole.NONE:
                return cell
        return next(iter(tile.cells.values()))

    @staticmethod
    def render_legend(*, mark_location: bool = False) -> str:
        return render_map_legend(
            mark_location=mark_location,
            pin_label="locations_index pin",
        )

    def render_macro_bbox(
        self,
        gx0: int,
        gy0: int,
        gx1: int,
        gy1: int,
        *,
        mark_location: bool = False,
    ) -> str:
        """Coarse overview: one symbol per macro-tile (center/rep light cell).

        Not the L0 mask SoT — prefer ``render_tile_light_grid`` / ``render_light_mask_mosaic``.
        """
        lines: list[str] = [
            format_grid_header(gx0, gx1, gy0, gy1, cell_size_m=self._tile_m),
            "pack L0 MACRO AGGREGATE (not mask SoT) — one symbol per macro-tile",
        ]
        for gy in range(gy1, gy0 - 1, -1):
            row_chars: list[str] = []
            for gx in range(gx0, gx1 + 1):
                if mark_location and (gx, gy) in self._pin_macros:
                    row_chars.append(LOCATION_PIN_SYMBOL)
                    continue
                tile = self._by_xy.get((gx, gy))
                if tile is None:
                    row_chars.append(" ")
                    continue
                cell = self._rep_cell(tile)
                row_chars.append(wire_symbol(cell) if cell is not None else " ")
            lines.append(f"{gy:4d} |{''.join(row_chars)}|")
        return "\n".join(lines)

    def render_macro(self, *, mark_location: bool = False) -> str:
        """Coarse overview aggregate — not L0 mask SoT."""
        if not self._by_xy:
            return ""
        xs = [gx for gx, _ in self._by_xy]
        ys = [gy for _, gy in self._by_xy]
        return self.render_macro_bbox(
            min(xs), min(ys), max(xs), max(ys), mark_location=mark_location,
        )

    def render_tile_light_grid(
        self,
        gx: int,
        gy: int,
        *,
        mark_location: bool = False,
    ) -> str:
        """L0 light-mask SoT for one macro-tile (side×side wire cells)."""
        tile = self._by_xy.get((gx, gy))
        if tile is None or tile.side <= 0:
            return ""
        pin_xy: set[tuple[int, int]] = set()
        if mark_location:
            for pin in self._pins:
                xy = _pin_light_xy(pin, tile, self._tile_m)
                if xy is not None:
                    pin_xy.add(xy)
        lines = [
            f"tile Gx={gx} Gy={gy}  (pack L0 light grid {tile.side}×{tile.side})",
            format_grid_header(
                0, tile.side - 1,
                0, tile.side - 1,
                cell_size_m=max(1, self._tile_m // tile.side),
                prefix="light ",
            ),
        ]
        for ty in range(tile.side - 1, -1, -1):
            row = "".join(
                LOCATION_PIN_SYMBOL
                if mark_location and (tx, ty) in pin_xy
                else (
                    wire_symbol(tile.cells[(tx, ty)], mark_pin=mark_location)
                    if (tx, ty) in tile.cells
                    else " "
                )
                for tx in range(tile.side)
            )
            lines.append(f"{ty:4d} |{row}|")
        return "\n".join(lines)

    def render_light_mask_mosaic(
        self,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
        mark_location: bool = False,
    ) -> str:
        """Concatenate per-tile light grids — primary pack smoke for L0 mask."""
        if not self._by_xy:
            return ""
        if gx0 is None or gy0 is None or gx1 is None or gy1 is None:
            keys = sorted(self._by_xy)
        else:
            keys = [
                (gx, gy)
                for gy in range(gy0, gy1 + 1)
                for gx in range(gx0, gx1 + 1)
                if (gx, gy) in self._by_xy
            ]
        parts = [
            self.render_tile_light_grid(gx, gy, mark_location=mark_location)
            for gx, gy in keys
        ]
        return "\n\n".join(p for p in parts if p)

    def render_all_tile_light_grids(
        self,
        *,
        mark_location: bool = False,
    ) -> dict[tuple[int, int], str]:
        out: dict[tuple[int, int], str] = {}
        for gx, gy in sorted(self._by_xy):
            text = self.render_tile_light_grid(gx, gy, mark_location=mark_location)
            if text:
                out[(gx, gy)] = text
        return out
