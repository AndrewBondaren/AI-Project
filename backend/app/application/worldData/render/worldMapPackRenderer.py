"""Pack-native L0 ASCII — mask + height SoT. Grade overlay is PAR-G5 omit."""

from __future__ import annotations

from collections import Counter

from app.application.worldData.pack.read.packRenderReadFacade import PackTileLightView
from app.application.worldData.render.fineTerrainAsciiKernel import (
    draw_int_grid,
    draw_symbol_grid,
)
from app.application.worldData.render.lightMapCells import wire_grade_symbol, wire_symbol
from app.application.worldData.render.lightMapPins import pin_macros, pin_world_xy
from app.application.worldData.render.lightMosaic import (
    collect_height_values,
    collect_mask_symbols,
    collect_tile_height_values,
    collect_tile_mask_symbols,
    render_all_tiles,
)
from app.application.worldData.render.lightMosaicFrame import (
    MosaicFrame,
    resolve_mosaic_frame,
)
from app.application.worldData.render.mapSymbols import (
    height_cell_width,
    render_height_legend,
    render_map_legend,
)
from app.application.worldData.render.worldMapGradeOverlay import (
    render_light_grade_mosaic as _grade_mosaic,
    render_tile_light_grade_grid as _tile_grade,
)
from app.application.worldData.render.worldMapMacroRender import (
    render_macro as _macro,
    render_macro_bbox as _macro_bbox,
)
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire


def _mosaic_title(kind: str, frame: MosaicFrame) -> str:
    return (
        f"pack L0 {kind} mosaic  "
        f"(macro Gx{frame.gx0}..Gx{frame.gx1} Gy{frame.gy0}..Gy{frame.gy1}, "
        f"{frame.side}×{frame.side} light cells per tile)"
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
        self._pins: list[LocationsIndexPin] = (
            list(pins.locations) if pins is not None else []
        )
        self._pin_macros = pin_macros(self._pins, self._tile_m)

    def tile_count(self) -> int:
        return len(self._by_xy)

    def _frame(
        self,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
    ) -> MosaicFrame | None:
        return resolve_mosaic_frame(
            self._by_xy, self._tile_m, gx0=gx0, gy0=gy0, gx1=gx1, gy1=gy1,
        )

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
        """Coarse overview: one symbol per macro-tile. Not L0 mask SoT."""
        return _macro_bbox(
            self._by_xy, self._tile_m, self._pin_macros,
            gx0, gy0, gx1, gy1, mark_location=mark_location,
        )

    def render_macro(self, *, mark_location: bool = False) -> str:
        """Coarse overview aggregate — not L0 mask SoT."""
        return _macro(
            self._by_xy, self._tile_m, self._pin_macros,
            mark_location=mark_location,
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
        return draw_symbol_grid(
            collect_tile_mask_symbols(
                tile, self._pins, self._tile_m, mark_location=mark_location,
            ),
            title=f"tile Gx={gx} Gy={gy}  (pack L0 light grid {tile.side}×{tile.side})",
            coord_prefix="light ",
            bounds=(0, tile.side - 1, 0, tile.side - 1),
            cell_size_m=max(1, self._tile_m // tile.side),
            x_rulers=False,
        )

    def render_tile_light_height_grid(self, gx: int, gy: int) -> str:
        """L0 ``surface_z`` ASCII for one macro-tile (fixed-width decimal cells)."""
        tile = self._by_xy.get((gx, gy))
        if tile is None or tile.side <= 0:
            return ""
        values = collect_tile_height_values(tile)
        zs = list(values.values())
        width = height_cell_width(zs)
        hist: Counter[int] = Counter(zs)
        ascii_h = draw_int_grid(
            values,
            title=f"tile Gx={gx} Gy={gy}  (pack L0 height grid {tile.side}×{tile.side})",
            extra_headers=[f"cell_width={width}"],
            coord_prefix="light ",
            width=width,
            bounds=(0, tile.side - 1, 0, tile.side - 1),
            cell_size_m=max(1, self._tile_m // tile.side),
        )
        if not hist:
            return ascii_h
        legend = render_height_legend(
            z_min=min(hist),
            z_max=max(hist),
            z_hist=dict(hist),
            cell_width=width,
        )
        return f"{ascii_h}\n\n{legend}"

    def render_light_mask_mosaic(
        self,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
        mark_location: bool = False,
    ) -> str:
        """One ASCII matrix: each light cell = one symbol; tiles placed by (gx, gy)."""
        frame = self._frame(gx0=gx0, gy0=gy0, gx1=gx1, gy1=gy1)
        if frame is None:
            return ""
        pin_wxy = (
            pin_world_xy(self._pins, frame, self._tile_m) if mark_location else set()
        )
        return draw_symbol_grid(
            collect_mask_symbols(
                self._by_xy, frame, pin_wxy=pin_wxy, mark_location=mark_location,
            ),
            title=_mosaic_title("light", frame),
            coord_prefix="light ",
            bounds=frame.bounds,
            cell_size_m=frame.light_m,
            x_rulers=False,
        )

    def render_light_height_mosaic(
        self,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
    ) -> tuple[str, str]:
        """``surface_z`` mosaic — decimal z per cell, pad width = max token in frame."""
        frame = self._frame(gx0=gx0, gy0=gy0, gx1=gx1, gy1=gy1)
        if frame is None:
            return "", render_height_legend()
        values = collect_height_values(self._by_xy, frame)
        zs = list(values.values())
        width = height_cell_width(zs)
        hist: Counter[int] = Counter(zs)
        ascii_h = draw_int_grid(
            values,
            title=_mosaic_title("height", frame),
            extra_headers=[f"cell_width={width}"],
            coord_prefix="light ",
            width=width,
            bounds=frame.bounds,
            cell_size_m=frame.light_m,
        )
        legend = render_height_legend(
            z_min=min(hist) if hist else None,
            z_max=max(hist) if hist else None,
            z_hist=dict(hist) if hist else None,
            cell_width=width,
        )
        return ascii_h, legend

    def render_tile_light_grade_grid(self, gx: int, gy: int) -> str:
        """L0 relief facing ASCII — PAR-G5 omit, leftover dump path."""
        return _tile_grade(self._by_xy, gx, gy, self._tile_m)

    def render_light_grade_mosaic(
        self,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
    ) -> tuple[str, str]:
        """Relief grade overlay. No grade cells → ``(\"\", \"\")``."""
        return _grade_mosaic(
            self._by_xy, self._tile_m, gx0=gx0, gy0=gy0, gx1=gx1, gy1=gy1,
        )

    def render_all_tile_light_grids(
        self,
        *,
        mark_location: bool = False,
    ) -> dict[tuple[int, int], str]:
        return render_all_tiles(
            self._by_xy,
            lambda gx, gy: self.render_tile_light_grid(
                gx, gy, mark_location=mark_location,
            ),
        )

    def render_all_tile_light_height_grids(self) -> dict[tuple[int, int], str]:
        return render_all_tiles(self._by_xy, self.render_tile_light_height_grid)

    def render_all_tile_light_grade_grids(self) -> dict[tuple[int, int], str]:
        return render_all_tiles(self._by_xy, self.render_tile_light_grade_grid)
