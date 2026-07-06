"""Dump world-map + per-location map_cells ASCII renders to ``.local/map-render/``.

Not a smoke test — no assertions. Requires running backend (path 2).

Usage:
    python scripts/render_maps.py world-test-all-001
    python scripts/render_maps.py world-test-all-001 --no-mark-locations
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
BASE = "http://localhost:8000/api"


def _ok(r: httpx.Response, ctx: str) -> None:
    if r.status_code >= 400:
        raise SystemExit(f"{ctx}: HTTP {r.status_code}\n{r.text[:3000]}")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render world + location map_cells to .local/")
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
        help="World map: @ on cells with location_uid (default: on)",
    )
    parser.add_argument(
        "--base-url",
        default=BASE,
        help=f"API base URL (default: {BASE})",
    )
    args = parser.parse_args()

    out_root = args.out or (REPO / ".local" / "map-render" / args.world_uid)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_root / stamp

    with httpx.Client(base_url=args.base_url, timeout=600.0) as c:
        r = c.get(
            f"/worlds/{args.world_uid}/map/render-world-grid",
            params={"mark_locations": str(args.mark_locations).lower()},
        )
        _ok(r, "render-world-grid")
        world = r.json()

        r = c.get(f"/worlds/{args.world_uid}/map/render-location-grids")
        _ok(r, "render-location-grids")
        locations_payload = r.json()

        r = c.get(f"/worlds/{args.world_uid}/map/render-world-tile-grids")
        _ok(r, "render-world-tile-grids")
        tiles_payload = r.json()

    world_path = run_dir / "world-map.txt"
    _write(
        world_path,
        f"{world.get('ascii', '')}\n\n--- legend ---\n{world.get('legend', '')}\n",
    )

    loc_root = run_dir / "locations"
    index: dict[str, object] = {
        "world_uid": args.world_uid,
        "stamp": stamp,
        "world_map": str(world_path.relative_to(REPO)),
        "mark_locations": args.mark_locations,
        "location_uids": locations_payload.get("location_uids", []),
        "locations": {},
    }

    for location_uid, entry in (locations_payload.get("locations") or {}).items():
        levels: dict[str, str] = entry.get("levels") or {}
        legend = entry.get("legend", "")
        loc_dir = loc_root / location_uid
        level_paths: dict[str, str] = {}
        combined: list[str] = [
            f"location_uid={location_uid}",
            f"indoor={entry.get('indoor')}",
            f"z_levels={entry.get('z_levels')}",
            "",
        ]
        for z_key, grid in sorted(levels.items(), key=lambda item: int(item[0])):
            z_path = loc_dir / f"z{z_key}.txt"
            body = f"{grid}\n\n--- legend ---\n{legend}\n"
            _write(z_path, body)
            level_paths[z_key] = str(z_path.relative_to(REPO))
            combined.append(f"=== z={z_key} ===")
            combined.append(grid)
            combined.append("")
        all_path = loc_dir / "all-levels.txt"
        combined.append(f"--- legend ---\n{legend}")
        _write(all_path, "\n".join(combined))
        index["locations"][location_uid] = {
            "indoor": entry.get("indoor"),
            "z_levels": entry.get("z_levels"),
            "all_levels": str(all_path.relative_to(REPO)),
            "levels": level_paths,
        }

    index_path = run_dir / "index.json"
    _write(index_path, json.dumps(index, ensure_ascii=False, indent=2))

    tiles_root = run_dir / "tiles"
    tile_index: dict[str, object] = {}
    for tile_key, entry in (tiles_payload.get("tiles") or {}).items():
        levels: dict[str, str] = entry.get("levels") or {}
        legend = entry.get("legend", "")
        tile_dir = tiles_root / tile_key
        surface = levels.get("-1") or levels.get("surface") or ""
        if not surface and levels:
            surface = next(iter(levels.values()))
        if surface:
            top_path = tile_dir / "surface-top.txt"
            _write(top_path, f"{surface}\n\n--- legend ---\n{legend}\n")
            tile_index[tile_key] = {
                "tile_gx": entry.get("tile_gx"),
                "tile_gy": entry.get("tile_gy"),
                "surface_top": str(top_path.relative_to(REPO)),
            }
    index["tiles"] = tile_index

    _write(index_path, json.dumps(index, ensure_ascii=False, indent=2))

    print(f"world-map: {world_path.relative_to(REPO)}")
    print(f"tiles: {len(tile_index)} macro cells")
    print(f"locations: {len(index['locations'])} with map_cells")
    for uid, meta in index["locations"].items():
        print(f"  {uid}: z={meta['z_levels']}")
    print(f"index: {index_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
