"""Shared FineTerrain column → ASCII symbols / grid draw (L2 location + wilderness).

Pure kernel: no pack I/O, no location_uid / tile gx knowledge.
Adapters supply title, headers, and column key space.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.application.worldData.render.gridAxes import format_grid_header
from app.application.worldData.render.mapSymbols import symbol_for_role_or_terrain
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainColumnWire, FineTerrainZRun


def run_covers(run: FineTerrainZRun, z: int) -> bool:
    z_lo, z_hi = min(run.z0, run.z1), max(run.z0, run.z1)
    return z_lo <= z <= z_hi


def terrain_at_z(col: FineTerrainColumnWire, z: int) -> str | None:
    for run in col.runs:
        if run_covers(run, z):
            return run.system_terrain
    return None


def top_terrain(col: FineTerrainColumnWire) -> tuple[int, str] | None:
    """Highest world-z sample in column → (z, system_terrain)."""
    best: tuple[int, str] | None = None
    for run in col.runs:
        z_hi = max(run.z0, run.z1)
        if best is None or z_hi > best[0]:
            best = (z_hi, run.system_terrain)
    return best


def z_endpoints(columns: Iterable[FineTerrainColumnWire]) -> list[int]:
    """Distinct run endpoints (not every integer in thick bands)."""
    zs: set[int] = set()
    for col in columns:
        for run in col.runs:
            zs.add(min(run.z0, run.z1))
            zs.add(max(run.z0, run.z1))
    return sorted(zs)


def symbols_surface_top(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    for key, col in cols.items():
        top = top_terrain(col)
        if top is not None:
            out[key] = symbol_for_role_or_terrain(system_terrain=top[1])
    return out


def symbols_at_z(
    cols: Mapping[tuple[int, int], FineTerrainColumnWire],
    z: int,
) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    for key, col in cols.items():
        terrain = terrain_at_z(col, z)
        if terrain is not None:
            out[key] = symbol_for_role_or_terrain(system_terrain=terrain)
    return out


def draw_symbol_grid(
    symbols: dict[tuple[int, int], str],
    *,
    title: str,
    extra_headers: list[str] | None = None,
    coord_prefix: str = "",
) -> str:
    """Draw ASCII from (x,y)→symbol. Empty symbols → empty string."""
    if not symbols:
        return ""
    xs = [x for x, _ in symbols]
    ys = [y for _, y in symbols]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    lines = [title]
    if extra_headers:
        lines.extend(extra_headers)
    lines.append(format_grid_header(x0, x1, y0, y1, cell_size_m=1, prefix=coord_prefix))
    for y in range(y1, y0 - 1, -1):
        row = "".join(symbols.get((x, y), " ") for x in range(x0, x1 + 1))
        lines.append(f"{y:4d} |{row}|")
    return "\n".join(lines)
