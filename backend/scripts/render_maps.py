"""Dump world ASCII renders to ``.local/map-render/`` — L0 light + L2 location_terrain.

Pack path (default after light bake):
  - ``render-world-grid`` → terrain mosaic + ``ascii_height`` (``world-height.txt``)
  - ``render-world-tile-grids`` → per-tile light + height (``levels.light`` / ``levels.height``)
  - ``render-location-grids`` → location_terrain when blob exists (may be empty after light-only)

Legacy path still works via the same endpoints (MapCell-backed levels).

Usage:
    python scripts/render_maps.py world-test-all-001
    python scripts/render_maps.py world-test-all-001 --no-mark-locations

Callable from ``initialize_world.py`` via ``dump_map_renders``.
"""
from __future__ import annotations

import argparse
import json
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
LEVEL_LIGHT = "light"
LEVEL_HEIGHT = "height"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _level_sort_key(key: str) -> tuple[int, int | str]:
    """Order: light/surface first, height next, then numeric z, then other strings."""
    if key in (LEVEL_LIGHT, LEVEL_SURFACE, "-1"):
        return (0, key)
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
        params={"mark_locations": str(mark_locations).lower()},
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
    _write(
        world_path,
        f"{world.get('ascii', '')}\n\n--- legend ---\n{world.get('legend', '')}\n",
    )

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
        loc_dir = loc_root / location_uid
        level_paths: dict[str, str] = {}
        combined: list[str] = [
            f"location_uid={location_uid}",
            f"indoor={entry.get('indoor')}",
            f"read_mode={entry.get('read_mode') or locations_payload.get('read_mode')}",
            f"z_levels={entry.get('z_levels')}",
            "",
        ]
        for z_key, grid in sorted(levels.items(), key=lambda item: _level_sort_key(str(item[0]))):
            safe = str(z_key).replace("/", "_")
            z_path = loc_dir / f"{safe}.txt"
            body = f"{grid}\n\n--- legend ---\n{legend}\n"
            _write(z_path, body)
            level_paths[str(z_key)] = str(z_path.relative_to(REPO))
            combined.append(f"=== {z_key} ===")
            combined.append(grid)
            combined.append("")
        all_path = loc_dir / "all-levels.txt"
        combined.append(f"--- legend ---\n{legend}")
        _write(all_path, "\n".join(combined))
        locations_meta[location_uid] = {
            "indoor": entry.get("indoor"),
            "z_levels": entry.get("z_levels"),
            "all_levels": str(all_path.relative_to(REPO)),
            "levels": level_paths,
        }

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
        # also write remaining levels for pack light + legacy z slices
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
    print(f"read_path={summary.get('read_path')} "
          f"world={summary.get('world_read_mode')} "
          f"locations={summary.get('locations_read_mode')}")
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
