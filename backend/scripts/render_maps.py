"""Dump world ASCII renders to ``.local/map-render/`` — L0 light + L2 location/wilderness.

Pack path (default after light bake):
  - ``render-world-grid`` → terrain mosaic + ``ascii_height`` (``world-height.txt``)
  - ``render-world-tile-grids`` → per-tile light + height (``levels.light`` / ``levels.height``)
  - ``render-location-grids`` → location_terrain when blob exists (may be empty after light-only)

Detailed L2 (after detailed_bake):
  - ``dump_detailed_renders`` → location_terrain + ``render-wilderness-tile-grid``
    Pack-read-only: each ``z/<n>.txt`` = cells already in FineTerrain runs (no generation).
    Default: ``surface`` / ``column_span`` / ``cliff_delta``, then one file per occupied world-z
    under ``wilderness/Gx*_Gy*/z/`` (fetched via ``?z=``, not one mega JSON).
  - does **not** re-dump L0 mosaic

Legacy path still works via the same endpoints (MapCell-backed levels).

Usage:
    python scripts/render_maps.py world-test-all-001
    python scripts/render_maps.py world-test-all-001 --no-mark-locations

Callable from ``initialize_world.py`` / ``detailed_bake.py`` via dump helpers.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from debug_api_helpers import BASE_URL, DebugApiError, _require_ok  # noqa: E402

LEVEL_SURFACE = "surface"
LEVEL_COLUMN_SPAN = "column_span"
LEVEL_CLIFF_DELTA = "cliff_delta"
LEVEL_LIGHT = "light"
LEVEL_HEIGHT = "height"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _level_sort_key(key: str) -> tuple[int, int | str]:
    """Order: light/surface first, column diagnostics, height, then numeric z."""
    if key in (LEVEL_LIGHT, LEVEL_SURFACE, "-1"):
        return (0, key)
    if key == LEVEL_COLUMN_SPAN:
        return (0, "z_column_span")
    if key == LEVEL_CLIFF_DELTA:
        return (0, "z_cliff_delta")
    if key == LEVEL_HEIGHT:
        return (0, "z_height")
    try:
        return (1, int(key))
    except ValueError:
        return (2, key)


def _pick_primary_level(levels: dict[str, str]) -> tuple[str, str] | None:
    for preferred in (LEVEL_LIGHT, LEVEL_SURFACE, "-1"):
        if preferred in levels and levels[preferred].strip():
            return preferred, levels[preferred]
    for key, grid in sorted(levels.items(), key=lambda item: _level_sort_key(item[0])):
        if grid.strip():
            return key, grid
    return None


def _write_level_bundle(
    out_dir: Path,
    *,
    header_lines: list[str],
    levels: dict[str, str],
    legend: str,
    combine_grids: bool = True,
) -> dict[str, object]:
    """Write per-level txt + all-levels.txt; return meta for index.

    When ``combine_grids=False``, ``all-levels.txt`` lists level file paths only
    (no concatenated ASCII) — used when dense z lives under ``z/``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    level_paths: dict[str, str] = {}
    combined: list[str] = [*header_lines, ""]
    for z_key, grid in sorted(levels.items(), key=lambda item: _level_sort_key(str(item[0]))):
        if not str(grid).strip():
            continue
        safe = str(z_key).replace("/", "_")
        z_path = out_dir / f"{safe}.txt"
        body = f"{grid}\n\n--- legend ---\n{legend}\n"
        _write(z_path, body)
        rel = str(z_path.relative_to(REPO))
        level_paths[str(z_key)] = rel
        combined.append(f"=== {z_key} ===")
        if combine_grids:
            combined.append(grid)
        else:
            combined.append(f"(file) {rel}")
        combined.append("")
    all_path = out_dir / "all-levels.txt"
    combined.append(f"--- legend ---\n{legend}")
    _write(all_path, "\n".join(combined))
    picked = _pick_primary_level(levels)
    primary_meta: dict[str, object] = {
        "all_levels": str(all_path.relative_to(REPO)),
        "levels": level_paths,
    }
    if picked is not None:
        primary_meta["primary_level"] = picked[0]
        primary_meta["primary"] = level_paths.get(picked[0])
    return primary_meta


def _wilderness_pack_renderer(world_uid: str, gx: int, gy: int):
    """Load FineTerrain chunks for one macro-tile from on-disk pack (dump helper)."""
    from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
    from app.application.worldData.pack.io.worldPackReader import WorldPackReader
    from app.application.worldData.render.wildernessTilePackRenderer import (
        WildernessTilePackRenderer,
    )

    pack_root = REPO / "db" / "worlds" / world_uid / "pack"
    if not (pack_root / "manifest.json").is_file():
        return None
    reader = WorldPackReader(WorldPackPaths(pack_root, world_uid))
    tile = reader.manifest.tile_entry(gx, gy)
    if tile is None:
        return None
    chunks = []
    for ref in tile.chunks:
        if not reader.chunk_exists(gx, gy, ref.cx, ref.cy):
            continue
        chunks.append(reader.read_wilderness_chunk(gx, gy, ref.cx, ref.cy))
    if not chunks:
        return None
    tile_size_m = int(reader.manifest.map_cell_size_m)
    return WildernessTilePackRenderer(
        chunks,
        tile_gx=gx,
        tile_gy=gy,
        tile_size_m=tile_size_m,
    )


def _write_wilderness_z_slices(
    client: httpx.Client,
    world_uid: str,
    *,
    gx: int,
    gy: int,
    occupied_z_levels: list[int],
    tile_dir: Path,
    legend: str,
) -> dict[str, str]:
    """Write ``z/<n>.txt`` for each occupied world-z (pack-local preferred).

    Pack path: one tile load + single-pass symbols → ASCII grid on the **shared
    mosaic frame** (empty cell = space; same x/y axes on every z — no shift).
    HTTP ``?z=`` fallback when pack is unavailable.
    """
    z_dir = tile_dir / "z"
    paths: dict[str, str] = {}
    occupied_filter = {int(z) for z in occupied_z_levels}
    renderer = _wilderness_pack_renderer(world_uid, gx, gy)
    source = "http"
    slice_format = "ascii_aligned"
    if renderer is not None:
        source = "pack"
        frame = renderer.mosaic_xy_bounds()
        print(
            f"  wilderness ({gx},{gy}): writing z-slice ASCII grids "
            f"(aligned frame={frame}) under z/",
            flush=True,
        )
        for i, (z_val, body) in enumerate(
            renderer.iter_occupied_z_levels_aligned(),
            start=1,
        ):
            if occupied_filter and int(z_val) not in occupied_filter:
                continue
            if not body.strip():
                continue
            z_path = z_dir / f"{int(z_val)}.txt"
            _write(z_path, f"{body}\n\n--- legend ---\n{legend}\n")
            paths[str(int(z_val))] = str(z_path.relative_to(REPO))
            if i == 1 or i % 200 == 0:
                print(f"    z-files {len(paths)} (last z={z_val})", flush=True)
        print(f"    z-files done: {len(paths)}", flush=True)
    else:
        occupied = sorted(occupied_filter)
        for z_val in occupied:
            r = client.get(
                f"/worlds/{world_uid}/map/render-wilderness-tile-grid",
                params={"gx": gx, "gy": gy, "z": z_val},
                timeout=600.0,
            )
            _require_ok(r, f"render-wilderness-tile-grid gx={gx} gy={gy} z={z_val}")
            payload = r.json()
            ascii_grid = str(payload.get("ascii") or "")
            if not ascii_grid.strip():
                continue
            z_path = z_dir / f"{int(z_val)}.txt"
            _write(z_path, f"{ascii_grid}\n\n--- legend ---\n{legend}\n")
            paths[str(int(z_val))] = str(z_path.relative_to(REPO))
    index_lines = [
        f"tile=({gx},{gy})",
        f"occupied_z_count={len(paths)}",
        f"files_written={len(paths)}",
        f"source={source}",
        f"slice_format={slice_format}",
        "",
        "z_files:",
    ]
    for key in sorted(paths.keys(), key=lambda k: int(k)):
        index_lines.append(f"  {key}: {paths[key]}")
    _write(tile_dir / "z-levels-index.txt", "\n".join(index_lines) + "\n")
    return paths


def dump_map_renders(
    client: httpx.Client,
    world_uid: str,
    *,
    out_root: Path | None = None,
    mark_locations: bool = True,
) -> dict[str, Any]:
    """Fetch pack/legacy render endpoints and write ASCII dumps under ``out_root``."""
    out_root = out_root or (REPO / ".local" / "map-render" / world_uid)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_root / stamp

    r = client.get(
        f"/worlds/{world_uid}/map/render-world-grid",
        params={"mark_locations": mark_locations},
    )
    _require_ok(r, "render-world-grid")
    world = r.json()

    r = client.get(f"/worlds/{world_uid}/map/render-location-grids")
    _require_ok(r, "render-location-grids")
    locations_payload = r.json()

    r = client.get(f"/worlds/{world_uid}/map/render-world-tile-grids")
    _require_ok(r, "render-world-tile-grids")
    tiles_payload = r.json()

    world_path = run_dir / "world-map.txt"
    legend = world.get("legend") or ""
    ascii_grid = str(world.get("ascii") or "")
    body = ascii_grid
    if legend:
        body = f"{ascii_grid}\n\n--- legend ---\n{legend}\n"
    _write(world_path, body)

    height_path: Path | None = None
    ascii_height = str(world.get("ascii_height") or "")
    if ascii_height.strip():
        height_path = run_dir / "world-height.txt"
        legend_h = world.get("legend_height") or ""
        body = ascii_height
        if legend_h:
            body = f"{ascii_height}\n\n--- legend ---\n{legend_h}\n"
        _write(height_path, body)

    loc_root = run_dir / "locations"
    location_uids = list(locations_payload.get("location_uids") or [])
    locations_meta: dict[str, object] = {}
    for location_uid, entry in (locations_payload.get("locations") or {}).items():
        levels: dict[str, str] = dict(entry.get("levels") or {})
        legend = entry.get("legend", "")
        meta = _write_level_bundle(
            loc_root / location_uid,
            header_lines=[
                f"location_uid={location_uid}",
                f"indoor={entry.get('indoor')}",
                f"read_mode={entry.get('read_mode') or locations_payload.get('read_mode')}",
                f"z_levels={entry.get('z_levels')}",
            ],
            levels=levels,
            legend=str(legend or ""),
        )
        meta["indoor"] = entry.get("indoor")
        meta["z_levels"] = entry.get("z_levels")
        locations_meta[location_uid] = meta

    tiles_root = run_dir / "tiles"
    tile_index: dict[str, object] = {}
    for tile_key, entry in (tiles_payload.get("tiles") or {}).items():
        levels = dict(entry.get("levels") or {})
        legend = entry.get("legend", "")
        tile_dir = tiles_root / tile_key
        picked = _pick_primary_level(levels)
        if picked is None:
            continue
        level_key, surface = picked
        top_path = tile_dir / f"{level_key}.txt"
        _write(top_path, f"{surface}\n\n--- legend ---\n{legend}\n")
        extra: dict[str, str] = {}
        for z_key, grid in levels.items():
            if z_key == level_key or not str(grid).strip():
                continue
            p = tile_dir / f"{str(z_key).replace('/', '_')}.txt"
            if str(z_key) == LEVEL_HEIGHT:
                _write(p, f"{grid}\n")
            else:
                _write(p, f"{grid}\n\n--- legend ---\n{legend}\n")
            extra[str(z_key)] = str(p.relative_to(REPO))
        tile_index[tile_key] = {
            "tile_gx": entry.get("tile_gx"),
            "tile_gy": entry.get("tile_gy"),
            "grid_kind": entry.get("grid_kind"),
            "primary_level": level_key,
            "primary": str(top_path.relative_to(REPO)),
            "levels": extra,
        }

    index: dict[str, object] = {
        "world_uid": world_uid,
        "stamp": stamp,
        "read_path": world.get("read_path") or tiles_payload.get("read_path"),
        "world_read_mode": world.get("read_mode"),
        "tiles_read_mode": tiles_payload.get("read_mode"),
        "locations_read_mode": locations_payload.get("read_mode"),
        "mark_locations": mark_locations,
        "world_map": str(world_path.relative_to(REPO)),
        "world_height": (
            str(height_path.relative_to(REPO)) if height_path is not None else None
        ),
        "location_uids": location_uids,
        "locations_with_terrain": list(locations_meta.keys()),
        "locations_index_pins": locations_payload.get("locations_index_pins") or [],
        "locations": locations_meta,
        "tiles": tile_index,
    }
    index_path = run_dir / "index.json"
    _write(index_path, json.dumps(index, ensure_ascii=False, indent=2))

    return {
        "run_dir": str(run_dir.relative_to(REPO)),
        "index": str(index_path.relative_to(REPO)),
        "world_map": str(world_path.relative_to(REPO)),
        "world_height": (
            str(height_path.relative_to(REPO)) if height_path is not None else None
        ),
        "tile_count": len(tile_index),
        "location_terrain_count": len(locations_meta),
        "location_pin_count": len(index["locations_index_pins"]),  # type: ignore[arg-type]
        "read_path": index.get("read_path"),
        "world_read_mode": index.get("world_read_mode"),
        "locations_read_mode": index.get("locations_read_mode"),
    }


def dump_detailed_renders(
    client: httpx.Client,
    world_uid: str,
    *,
    out_root: Path | None = None,
    wilderness_tiles: list[tuple[int, int]] | None = None,
    location_uids: list[str] | None = None,
    include_z_slices: bool = False,
    write_z_slice_files: bool = True,
) -> dict[str, Any]:
    """Dump L2 detailed ASCII only — location_terrain + wilderness tile mosaics.

    Renderer is pack-read-only: z slices = ``terrain_at_z`` over existing FineTerrain
    runs (empty cell at z ⇒ blank). Does not call L0 ``render-world-grid``.

    Wilderness default: base call without dense ASCII in JSON; each occupied world-z
    is fetched with ``?z=`` and written to ``wilderness/.../z/<n>.txt``.
    """
    out_root = out_root or (
        REPO / ".local" / "map-render" / world_uid / "detailed-bake" / "after-detailed"
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_root / stamp

    wilderness_tiles = list(wilderness_tiles or [])
    location_uids = list(location_uids or [])

    locations_meta: dict[str, object] = {}
    if location_uids:
        r = client.get(f"/worlds/{world_uid}/map/render-location-grids")
        _require_ok(r, "render-location-grids")
        locations_payload = r.json()
        all_locs = locations_payload.get("locations") or {}
        for location_uid in location_uids:
            entry = all_locs.get(location_uid)
            if entry is None:
                continue
            levels = dict(entry.get("levels") or {})
            meta = _write_level_bundle(
                run_dir / "locations" / location_uid,
                header_lines=[
                    f"location_uid={location_uid}",
                    f"read_mode={entry.get('read_mode') or locations_payload.get('read_mode')}",
                    f"z_levels={entry.get('z_levels')}",
                ],
                levels=levels,
                legend=str(entry.get("legend") or ""),
            )
            meta["z_levels"] = entry.get("z_levels")
            locations_meta[location_uid] = meta

    wilderness_meta: dict[str, object] = {}
    for gx, gy in wilderness_tiles:
        # Dense z ASCII must not ride in one JSON — use occupied_z_levels + ?z= files.
        bulk_z = bool(include_z_slices) and not write_z_slice_files
        r = client.get(
            f"/worlds/{world_uid}/map/render-wilderness-tile-grid",
            params={
                "gx": gx,
                "gy": gy,
                "include_z_slices": bulk_z,
                "include_column_diagnostics": True,
            },
            timeout=600.0,
        )
        _require_ok(r, f"render-wilderness-tile-grid gx={gx} gy={gy}")
        payload = r.json()
        tile_key = f"Gx{gx}_Gy{gy}"
        tile_dir = run_dir / "wilderness" / tile_key
        levels: dict[str, str] = dict(payload.get("levels") or {})
        if payload.get("ascii") and not levels:
            key = LEVEL_SURFACE if payload.get("z") is None else str(payload["z"])
            levels[key] = str(payload["ascii"])
        # When writing per-z files, keep base bundle free of numeric z grids.
        if write_z_slice_files:
            levels = {
                k: v
                for k, v in levels.items()
                if k in (LEVEL_SURFACE, LEVEL_COLUMN_SPAN, LEVEL_CLIFF_DELTA)
                or not str(k).lstrip("-").isdigit()
            }
        legend = str(payload.get("legend") or "")
        occupied_raw = payload.get("occupied_z_levels") or []
        occupied: list[int] = []
        for item in occupied_raw:
            try:
                occupied.append(int(item))
            except (TypeError, ValueError):
                continue
        occupied = sorted(set(occupied))
        meta = _write_level_bundle(
            tile_dir,
            header_lines=[
                f"tile=({gx},{gy})",
                f"read_mode={payload.get('read_mode')}",
                f"chunks_listed={payload.get('chunks_listed')}",
                f"chunks_loaded={payload.get('chunks_loaded')}",
                f"column_count={payload.get('column_count')}",
                f"wilderness_refine_status={payload.get('wilderness_refine_status')}",
                f"occupied_z_levels={occupied}",
            ],
            levels=levels,
            legend=legend,
            combine_grids=not write_z_slice_files,
        )
        z_slice_paths: dict[str, str] = {}
        if write_z_slice_files:
            z_slice_paths = _write_wilderness_z_slices(
                client,
                world_uid,
                gx=gx,
                gy=gy,
                occupied_z_levels=occupied,
                tile_dir=tile_dir,
                legend=legend,
            )
            if z_slice_paths and not occupied:
                occupied = sorted(int(k) for k in z_slice_paths)
            meta["z_slice_files"] = z_slice_paths
            meta["z_levels_index"] = str(
                (tile_dir / "z-levels-index.txt").relative_to(REPO)
            )
            meta["occupied_z_levels"] = occupied
        meta.update(
            {
                "tile_gx": gx,
                "tile_gy": gy,
                "read_mode": payload.get("read_mode"),
                "chunks_listed": payload.get("chunks_listed"),
                "chunks_loaded": payload.get("chunks_loaded"),
                "column_count": payload.get("column_count"),
                "wilderness_refine_status": payload.get("wilderness_refine_status"),
                "occupied_z_levels": occupied,
                "z_slice_file_count": len(z_slice_paths),
            }
        )
        wilderness_meta[tile_key] = meta

    index: dict[str, object] = {
        "world_uid": world_uid,
        "stamp": stamp,
        "kind": "detailed_l2",
        "location_uids": list(locations_meta.keys()),
        "locations": locations_meta,
        "wilderness_tiles": wilderness_meta,
    }
    index_path = run_dir / "index.json"
    _write(index_path, json.dumps(index, ensure_ascii=False, indent=2))

    latest = out_root / "latest"
    if latest.exists() or latest.is_symlink():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink()
    try:
        latest.symlink_to(run_dir.resolve(), target_is_directory=True)
    except OSError:
        shutil.copytree(run_dir, latest)

    return {
        "run_dir": str(run_dir.relative_to(REPO)),
        "index": str(index_path.relative_to(REPO)),
        "latest": str(latest.relative_to(REPO)),
        "location_terrain_count": len(locations_meta),
        "wilderness_tile_count": len(wilderness_meta),
        "wilderness_tiles": wilderness_meta,
        "wilderness_tiles_with_grid": sum(
            1
            for m in wilderness_meta.values()
            if isinstance(m, dict) and m.get("primary")
        ),
        "wilderness_z_slice_file_count": sum(
            int(m.get("z_slice_file_count") or 0)
            for m in wilderness_meta.values()
            if isinstance(m, dict)
        ),
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print(f"world-map: {summary['world_map']}")
    if summary.get("world_height"):
        print(f"world-height: {summary['world_height']}")
    print(f"tiles (L0 light / fine): {summary['tile_count']}")
    print(
        f"locations L2 terrain: {summary['location_terrain_count']} "
        f"(pins in index: {summary['location_pin_count']})"
    )
    if summary["location_terrain_count"] == 0:
        print(
            "note: no location_terrain blobs yet — light bake is L0 only; "
            "L2 appears after entry refine / location bake"
        )
    print(
        f"read_path={summary.get('read_path')} "
        f"world={summary.get('world_read_mode')} "
        f"locations={summary.get('locations_read_mode')}"
    )
    print(f"index: {summary['index']}")


def _print_detailed_summary(summary: dict[str, Any]) -> None:
    print(f"detailed L2 locations: {summary['location_terrain_count']}")
    print(
        f"detailed L2 wilderness tiles: {summary['wilderness_tile_count']} "
        f"(with grid: {summary['wilderness_tiles_with_grid']})"
    )
    z_files = int(summary.get("wilderness_z_slice_file_count") or 0)
    if z_files:
        print(f"wilderness z-slice files: {z_files}")
    print(f"run_dir: {summary['run_dir']}")
    print(f"latest: {summary.get('latest')}")
    print(f"index: {summary['index']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render world L0 + location L2 ASCII dumps to .local/",
    )
    parser.add_argument("world_uid", help="World UID in running backend DB")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output root (default: .local/map-render/{world_uid})",
    )
    parser.add_argument(
        "--mark-locations",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="World map: @ on locations_index pins / location_uid (default: on)",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"API base URL (default: {BASE_URL})",
    )
    args = parser.parse_args()

    try:
        with httpx.Client(base_url=args.base_url, timeout=600.0) as client:
            summary = dump_map_renders(
                client,
                args.world_uid,
                out_root=args.out,
                mark_locations=args.mark_locations,
            )
    except DebugApiError as exc:
        raise SystemExit(str(exc)) from exc

    _print_summary(summary)


if __name__ == "__main__":
    main()
