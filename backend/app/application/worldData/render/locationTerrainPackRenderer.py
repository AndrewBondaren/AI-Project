"""Pack-native location terrain ASCII — ``l.{uid}.terrain.zst`` (FineTerrainChunkWire)."""

from __future__ import annotations

from app.application.worldData.render.gridAxes import format_grid_header
from app.application.worldData.render.mapSymbols import render_map_legend, symbol_for_role_or_terrain
from app.application.worldData.render.renderPayloads import LEVEL_SURFACE
from app.dataModel.worldPack.fineTerrainChunkWire import (
    FineTerrainChunkWire,
    FineTerrainColumnWire,
    FineTerrainZRun,
)
from app.dataModel.worldPack.territoryVolume import TerritoryVolume


def _run_covers(run: FineTerrainZRun, z: int) -> bool:
    z_lo, z_hi = min(run.z0, run.z1), max(run.z0, run.z1)
    return z_lo <= z <= z_hi


def _terrain_at_z(col: FineTerrainColumnWire, z: int) -> str | None:
    for run in col.runs:
        if _run_covers(run, z):
            return run.system_terrain
    return None


def _top_terrain(col: FineTerrainColumnWire) -> tuple[int, str] | None:
    """Highest world-z sample in column → (z, system_terrain)."""
    best: tuple[int, str] | None = None
    for run in col.runs:
        z_hi = max(run.z0, run.z1)
        if best is None or z_hi > best[0]:
            best = (z_hi, run.system_terrain)
    return best


class LocationTerrainPackRenderer:
    """L2 location terrain from pack blob — local (lx,ly) + absolute world z."""

    def __init__(
        self,
        chunk: FineTerrainChunkWire,
        *,
        volume: TerritoryVolume,
        location_uid: str,
    ) -> None:
        self._chunk = chunk
        self._volume = volume
        self.location_uid = location_uid
        self._cols: dict[tuple[int, int], FineTerrainColumnWire] = {
            (c.lx, c.ly): c for c in chunk.columns
        }

    @staticmethod
    def render_legend() -> str:
        return render_map_legend(mark_location=False)

    def _world_xy(self, lx: int, ly: int) -> tuple[int, int]:
        return self._volume.x0 + lx, self._volume.y0 + ly

    def _bbox_local(self) -> tuple[int, int, int, int] | None:
        if not self._cols:
            return None
        xs = [lx for lx, _ in self._cols]
        ys = [ly for _, ly in self._cols]
        return min(xs), min(ys), max(xs), max(ys)

    def render_surface_top(self) -> str:
        if not self._cols:
            return ""
        tops: dict[tuple[int, int], str] = {}
        for key, col in self._cols.items():
            top = _top_terrain(col)
            if top is not None:
                tops[key] = symbol_for_role_or_terrain(system_terrain=top[1])
        return self._draw_local_grid(
            tops,
            title=f"location={self.location_uid}  (pack location_terrain, top z)",
        )

    def render_level(self, z: int) -> str:
        if not self._cols:
            return ""
        level: dict[tuple[int, int], str] = {}
        for key, col in self._cols.items():
            terrain = _terrain_at_z(col, z)
            if terrain is not None:
                level[key] = symbol_for_role_or_terrain(system_terrain=terrain)
        if not level:
            return ""
        return self._draw_local_grid(
            level,
            title=f"location={self.location_uid} z={z}  (pack location_terrain)",
        )

    def z_levels(self) -> list[int]:
        """Distinct run endpoints (not every integer in thick bands)."""
        zs: set[int] = set()
        for col in self._cols.values():
            for run in col.runs:
                zs.add(min(run.z0, run.z1))
                zs.add(max(run.z0, run.z1))
        return sorted(zs)

    def render_all_levels(self) -> dict[str, str]:
        """Keys: ``LEVEL_SURFACE`` plus decimal world-z run endpoints."""
        out: dict[str, str] = {}
        surface = self.render_surface_top()
        if surface:
            out[LEVEL_SURFACE] = surface
        for z in self.z_levels():
            text = self.render_level(z)
            if text.strip():
                out[str(z)] = text
        return out

    def _draw_local_grid(self, symbols: dict[tuple[int, int], str], *, title: str) -> str:
        bbox = self._bbox_local()
        if bbox is None or not symbols:
            return ""
        lx0, ly0, lx1, ly1 = bbox
        wx0, wy0 = self._world_xy(lx0, ly0)
        wx1, wy1 = self._world_xy(lx1, ly1)
        vol = self._volume
        lines = [
            title,
            (
                f"territory meters x: {vol.x0}..{vol.x1}  y: {vol.y0}..{vol.y1}  "
                f"z: {vol.z0}..{vol.z1}"
            ),
            format_grid_header(lx0, lx1, ly0, ly1, cell_size_m=1, prefix="local "),
            f"world meters x: {wx0}..{wx1 + 1}  y: {wy0}..{wy1 + 1}",
        ]
        for ly in range(ly1, ly0 - 1, -1):
            row = "".join(
                symbols.get((lx, ly), " ")
                for lx in range(lx0, lx1 + 1)
            )
            lines.append(f"{ly:4d} |{row}|")
        return "\n".join(lines)
