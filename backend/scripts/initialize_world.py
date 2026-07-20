"""World initialization smoke — import fixture, L0 pack bake, optional entry job.

Uses ``POST …/map/pack/bake`` (L0 only — Job boundaries).
Entry/L2 is a **separate** job: ``--entry`` → ``POST …/map/refine-from-entry``.
Requires running backend (``npm run backend``) — agents must not start it.

Examples:
  python scripts/initialize_world.py --fixture ../fixtures/world_terrain_test.json
  python scripts/initialize_world.py --fixture ../fixtures/world_test_gen.json --entry
  python scripts/initialize_world.py --no-render
  python scripts/smoke_world_pack.py --fixture ../fixtures/world_terrain_test.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from app.application.worldData.pack.import_.importLevels import filter_bundle_for_export
from debug_api_helpers import (
    DebugApiError,
    _require_ok,
    api_clear_map,
    api_client,
    api_refine_from_entry,
)
from debug_surface_helpers import (
    api_list_bootstrap_tiles,
    api_loading_progress,
    api_pack_bake,
)
from render_maps import _print_summary, dump_map_renders


def _import_fixture(client, path: str) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    bundle = filter_bundle_for_export(raw, "skeleton")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8",
    ) as tmp:
        json.dump(bundle, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    try:
        r = client.post("/worlds/import", data={"path": tmp_path})
        _require_ok(r, f"POST /worlds/import {path}")
        data = r.json()
        if not isinstance(data, dict):
            raise DebugApiError(f"import: expected object, got {type(data)}")
        return data
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _fixture_world_uid(fixture: Path) -> str:
    data = json.loads(fixture.read_text(encoding="utf-8"))
    return data.get("world", data)["world_uid"]


def _resolve_entry_anchor(
    client,
    world_uid: str,
    *,
    anchor_x: int | None,
    anchor_y: int | None,
) -> tuple[int, int]:
    if anchor_x is not None and anchor_y is not None:
        return int(anchor_x), int(anchor_y)
    r = client.get(f"/worlds/{world_uid}/locations")
    _require_ok(r, f"GET locations {world_uid}")
    locs = r.json()
    if not isinstance(locs, list):
        raise SystemExit(f"locations: expected list, got {type(locs)}")
    for loc in locs:
        mx, my = loc.get("map_x"), loc.get("map_y")
        if mx is not None and my is not None:
            return int(mx), int(my)
    raise SystemExit(
        "--entry requires --anchor-x/--anchor-y or a location with map_x/map_y",
    )


def _loading_world_map(progress: dict) -> dict[str, Any]:
    wm = progress.get("worldMapLoading") or progress.get("world_map") or {}
    return wm if isinstance(wm, dict) else {}


def _build_pack_bake_metrics(
    bake: dict,
    *,
    started_at: datetime,
    finished_at: datetime,
    http_elapsed_s: float,
) -> dict[str, Any]:
    terrain = bake.get("terrain") or {}
    climate = bake.get("climate") or {}
    progress = bake.get("loading_progress") or {}
    wm = _loading_world_map(progress)
    server_s = bake.get("elapsed_s")
    return {
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "http_elapsed_s": round(http_elapsed_s, 2),
        "server_bake_elapsed_s": round(server_s, 2) if server_s is not None else None,
        "pack_mode": bake.get("pack_mode"),
        "tiles_pct": wm.get("tiles_pct"),
        "locations_pct": wm.get("locations_pct"),
        "wilderness_pct": wm.get("wilderness_pct"),
        "tiles_ready": wm.get("tiles_ready"),
        "tiles_total": wm.get("tiles_total"),
        "world_map_cells": bake.get("world_map_cells"),
        "terrain_succeeded": terrain.get("succeeded"),
        "terrain_failed": terrain.get("failed"),
        "climate_succeeded": climate.get("succeeded"),
        "climate_coarse_samples": bake.get("climate_coarse_samples"),
        "climate_fine_tiles": bake.get("climate_fine_tiles"),
        "has_climate_coarse": progress.get("has_climate_coarse"),
        "climate_status": (progress.get("localGridLoading") or {}).get("climate_status"),
        "chunks_blocking_done": bake.get("chunks_done"),
        "chunks_blocking_total": bake.get("chunks_total"),
        "refine_queue_depth": bake.get("refine_queue_depth"),
        "terrain_workers": bake.get("terrain_workers"),
    }


def _print_metrics(title: str, metrics: dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    width = max(len(str(k)) for k in metrics)
    for key, value in metrics.items():
        print(f"{key:<{width}}  {value}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Bootstrap world via World Pack L0 bake (pack/bake); optional --entry job",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO / "fixtures" / "world_terrain_test.json",
    )
    parser.add_argument("--world-uid", default=None, help="defaults to fixture world_uid")
    parser.add_argument(
        "--max-tiles",
        type=int,
        default=None,
        help="debug-only light bake cap; omit/0 = uncapped (all location tiles)",
    )
    parser.add_argument(
        "--mode",
        choices=("light", "full"),
        default="light",
        help="pack bake mode: light (location tiles) or full (entire world_bounds)",
    )
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--skip-clear", action="store_true")
    parser.add_argument(
        "--entry",
        action="store_true",
        help="After L0 bake: separate POST refine-from-entry (L2 scene + bg schedule)",
    )
    parser.add_argument(
        "--render",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After bake: dump L0 ASCII via render API (default: on)",
    )
    parser.add_argument(
        "--render-out",
        type=Path,
        default=None,
        help="Render output root (default: .local/map-render/{world_uid})",
    )
    parser.add_argument(
        "--mark-locations",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Render: @ pins on world map (default: on)",
    )
    parser.add_argument(
        "--anchor-x",
        type=int,
        default=None,
        help="Entry job anchor meters (with --entry; else first location map_x)",
    )
    parser.add_argument(
        "--anchor-y",
        type=int,
        default=None,
        help="Entry job anchor meters (with --entry; else first location map_y)",
    )
    args = parser.parse_args()

    fixture = args.fixture.resolve()
    if not fixture.is_file():
        raise SystemExit(f"fixture not found: {fixture}")

    world_uid = args.world_uid or _fixture_world_uid(fixture)

    with api_client() as client:
        if not args.skip_import:
            imp = _import_fixture(client, str(fixture))
            print("import:", {k: v for k, v in imp.items() if k not in ("rolled_back", "rollback_reason")})

        if not args.skip_clear:
            api_clear_map(client, world_uid)
            print(f"cleared map patches: {world_uid}")
            print(
                "note: pack dir on disk is not deleted — rebake overwrites tiles; "
                "wipe pack folder manually for a clean slate",
            )

        preview = api_list_bootstrap_tiles(client, world_uid, max_tiles=args.max_tiles)
        print(
            f"bootstrap tiles (preview): {preview.get('tile_count')} "
            f"max_tiles={preview.get('max_tiles')}"
        )
        for tile in preview.get("tiles") or []:
            print(f"  Gx{tile['gx']}_Gy{tile['gy']}")

        started_at = datetime.now().astimezone()
        t0 = time.perf_counter()
        bake = api_pack_bake(
            client,
            world_uid,
            mode=args.mode,
            max_tiles=args.max_tiles if args.mode == "light" else None,
        )
        http_elapsed_s = time.perf_counter() - t0
        finished_at = datetime.now().astimezone()

        if not bake.get("loading_progress"):
            bake = {**bake, "loading_progress": api_loading_progress(client, world_uid)}

        _print_metrics(
            "pack bake metrics (L0 only)",
            _build_pack_bake_metrics(
                bake,
                started_at=started_at,
                finished_at=finished_at,
                http_elapsed_s=http_elapsed_s,
            ),
        )

        if args.entry:
            ax, ay = _resolve_entry_anchor(
                client, world_uid, anchor_x=args.anchor_x, anchor_y=args.anchor_y,
            )
            print(f"\n=== entry job (separate from bake) anchor=({ax},{ay}) ===")
            t1 = time.perf_counter()
            entry = api_refine_from_entry(client, world_uid, x=ax, y=ay)
            print(
                f"refine-from-entry: {time.perf_counter() - t1:.2f}s "
                f"chunks_done={entry.get('chunks_done')} "
                f"queue={entry.get('refine_queue_depth')}"
            )

        if args.render:
            print("\n=== map render (L0; L2 only if --entry ran) ===")
            summary = dump_map_renders(
                client,
                world_uid,
                out_root=args.render_out,
                mark_locations=args.mark_locations,
            )
            _print_summary(summary)


if __name__ == "__main__":
    main()
