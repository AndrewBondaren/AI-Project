"""Pack-native L0 ASCII — ``WorldMapCellWire`` + ``locations_index`` (no MapCell round-trip)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.application.worldData.pack.read.packMapHelpers import (
    tile_index,
    world_map_sample_index,
)
from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.gridAxes import format_grid_header
from app.application.worldData.render.mapSymbols import (
    LOCATION_PIN_SYMBOL,
    format_height_cell,
    height_cell_width,
    join_height_row,
    render_height_legend,
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


@dataclass(frozen=True)
class _MosaicFrame:
    gx0: int
    gy0: int
    gx1: int
    gy1: int
    side: int
    light_m: int
    lx0: int
    lx1: int
    ly0: int
    ly1: int


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

    def tile_count(self) -> int:
        return len(self._by_xy)

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

    def _mosaic_frame(
        self,
        *,
        gx0: int | None,
        gy0: int | None,
        gx1: int | None,
        gy1: int | None,
    ) -> _MosaicFrame | None:
        """Build mosaic frame. Prefer caller bbox (MLB-12 world_bounds / AABB).

        When bbox omitted and tiles exist — fall back to baked tile extent only.
        Missing macro-tiles inside the frame render as spaces (unmapped).
        """
        if gx0 is None or gy0 is None or gx1 is None or gy1 is None:
            if not self._by_xy:
                return None
            xs = [gx for gx, _ in self._by_xy]
            ys = [gy for _, gy in self._by_xy]
            gx0, gx1 = min(xs), max(xs)
            gy0, gy1 = min(ys), max(ys)
        elif not self._by_xy:
            # Frame known (bounds) but no baked tiles yet — still need side from caller.
            # Without any tile we cannot know light side; empty mosaic.
            return None

        side = 0
        for gy in range(gy0, gy1 + 1):
            for gx in range(gx0, gx1 + 1):
                tile = self._by_xy.get((gx, gy))
                if tile is not None and tile.side > 0:
                    side = tile.side
                    break
            if side > 0:
                break
        if side <= 0:
            for tile in self._by_xy.values():
                if tile.side > 0:
                    side = tile.side
                    break
        if side <= 0:
            return None

        return _MosaicFrame(
            gx0=gx0,
            gy0=gy0,
            gx1=gx1,
            gy1=gy1,
            side=side,
            light_m=max(1, self._tile_m // side),
            lx0=gx0 * side,
            lx1=(gx1 + 1) * side - 1,
            ly0=gy0 * side,
            ly1=(gy1 + 1) * side - 1,
        )

    def _pin_world_xy(self, frame: _MosaicFrame) -> set[tuple[int, int]]:
        pin_wxy: set[tuple[int, int]] = set()
        for pin in self._pins:
            pgx, lx = tile_index(pin.map_x, self._tile_m)
            pgy, ly = tile_index(pin.map_y, self._tile_m)
            if not (frame.gx0 <= pgx <= frame.gx1 and frame.gy0 <= pgy <= frame.gy1):
                continue
            tx = world_map_sample_index(lx, self._tile_m, frame.side)
            ty = world_map_sample_index(ly, self._tile_m, frame.side)
            pin_wxy.add((pgx * frame.side + tx, pgy * frame.side + ty))
        return pin_wxy

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

    def render_tile_light_height_grid(self, gx: int, gy: int) -> str:
        """L0 ``surface_z`` ASCII for one macro-tile (fixed-width decimal cells)."""
        tile = self._by_xy.get((gx, gy))
        if tile is None or tile.side <= 0:
            return ""
        zs = [int(cell.surface_z) for cell in tile.cells.values()]
        width = height_cell_width(zs)
        hist: Counter[int] = Counter(zs)
        lines = [
            f"tile Gx={gx} Gy={gy}  (pack L0 height grid {tile.side}×{tile.side})",
            format_grid_header(
                0, tile.side - 1,
                0, tile.side - 1,
                cell_size_m=max(1, self._tile_m // tile.side),
                prefix="light ",
            ),
            f"cell_width={width}",
        ]
        for ty in range(tile.side - 1, -1, -1):
            row = [
                format_height_cell(
                    None if (tx, ty) not in tile.cells else tile.cells[(tx, ty)].surface_z,
                    width=width,
                )
                for tx in range(tile.side)
            ]
            lines.append(f"{ty:4d} |{join_height_row(row)}|")
        if hist:
            lines.append("")
            lines.append(
                render_height_legend(
                    z_min=min(hist),
                    z_max=max(hist),
                    z_hist=dict(hist),
                    cell_width=width,
                ),
            )
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
        """One ASCII matrix: each light cell = one symbol; tiles placed by (gx, gy).

        Missing macro-tiles inside the bbox are spaces. Per-tile dumps stay in
        ``render_tile_light_grid`` / ``render_all_tile_light_grids``.
        """
        frame = self._mosaic_frame(gx0=gx0, gy0=gy0, gx1=gx1, gy1=gy1)
        if frame is None:
            return ""

        pin_wxy = self._pin_world_xy(frame) if mark_location else set()
        lines: list[str] = [
            (
                f"pack L0 light mosaic  "
                f"(macro Gx{frame.gx0}..Gx{frame.gx1} Gy{frame.gy0}..Gy{frame.gy1}, "
                f"{frame.side}×{frame.side} light cells per tile)"
            ),
            format_grid_header(
                frame.lx0, frame.lx1, frame.ly0, frame.ly1,
                cell_size_m=frame.light_m, prefix="light ",
            ),
        ]
        label_w = max(4, len(str(frame.ly0)), len(str(frame.ly1)))
        for wy in range(frame.ly1, frame.ly0 - 1, -1):
            row: list[str] = []
            for wx in range(frame.lx0, frame.lx1 + 1):
                if mark_location and (wx, wy) in pin_wxy:
                    row.append(LOCATION_PIN_SYMBOL)
                    continue
                gx, tx = divmod(wx, frame.side)
                gy, ty = divmod(wy, frame.side)
                tile = self._by_xy.get((gx, gy))
                if tile is None or (tx, ty) not in tile.cells:
                    row.append(" ")
                    continue
                row.append(
                    wire_symbol(tile.cells[(tx, ty)], mark_pin=mark_location),
                )
            lines.append(f"{wy:{label_w}d} |{''.join(row)}|")
        return "\n".join(lines)

    def render_light_height_mosaic(
        self,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
    ) -> tuple[str, str]:
        """``surface_z`` mosaic — decimal z per cell, pad width = max token in frame."""
        frame = self._mosaic_frame(gx0=gx0, gy0=gy0, gx1=gx1, gy1=gy1)
        if frame is None:
            return "", render_height_legend()

        zs: list[int] = []
        for wy in range(frame.ly0, frame.ly1 + 1):
            for wx in range(frame.lx0, frame.lx1 + 1):
                gx, tx = divmod(wx, frame.side)
                gy, ty = divmod(wy, frame.side)
                tile = self._by_xy.get((gx, gy))
                cell = None if tile is None else tile.cells.get((tx, ty))
                if cell is not None:
                    zs.append(int(cell.surface_z))
        width = height_cell_width(zs)
        hist: Counter[int] = Counter(zs)

        lines: list[str] = [
            (
                f"pack L0 height mosaic  "
                f"(macro Gx{frame.gx0}..Gx{frame.gx1} Gy{frame.gy0}..Gy{frame.gy1}, "
                f"{frame.side}×{frame.side} light cells per tile)"
            ),
            format_grid_header(
                frame.lx0, frame.lx1, frame.ly0, frame.ly1,
                cell_size_m=frame.light_m, prefix="light ",
            ),
            f"cell_width={width}",
        ]
        label_w = max(4, len(str(frame.ly0)), len(str(frame.ly1)))
        for wy in range(frame.ly1, frame.ly0 - 1, -1):
            row: list[str] = []
            for wx in range(frame.lx0, frame.lx1 + 1):
                gx, tx = divmod(wx, frame.side)
                gy, ty = divmod(wy, frame.side)
                tile = self._by_xy.get((gx, gy))
                cell = None if tile is None else tile.cells.get((tx, ty))
                row.append(
                    format_height_cell(
                        None if cell is None else cell.surface_z,
                        width=width,
                    ),
                )
            lines.append(f"{wy:{label_w}d} |{join_height_row(row)}|")

        legend = render_height_legend(
            z_min=min(hist) if hist else None,
            z_max=max(hist) if hist else None,
            z_hist=dict(hist) if hist else None,
            cell_width=width,
        )
        return "\n".join(lines), legend

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

    def render_all_tile_light_height_grids(self) -> dict[tuple[int, int], str]:
        out: dict[tuple[int, int], str] = {}
        for gx, gy in sorted(self._by_xy):
            text = self.render_tile_light_height_grid(gx, gy)
            if text:
                out[(gx, gy)] = text
        return out
