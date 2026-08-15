"""Smoke: detailed_bake L2 — location territory and/or wilderness tiles.

Assumes the world already has L0 parent light (after light_and_full_bake / full).
Does **not** wipe pack, re-import, or run entry/bg refine.

**Logs (stdout/stderr → terminal + file):**

- ``.local/map-render/{uid}/detailed-bake/detailed-bake-latest.log`` — **весь** прогон
  (plan, bake poll, after, render dump); stamped ``detailed-bake-{stamp}.log``
- ``tiles/gx{G}_gy{Y}/tile-latest.log`` — тот же bake-poll **ещё** в per-tile файл
- ``locations/{location_uid}/location-latest.log`` — то же для location

Heartbeat (``[online]`` chunks, ``z-files`` / ``grade_z-files``): **всегда в файл**.
В терминал — только ``--debug`` / ``DEBUG_PROGRESS=1``.
SoT: ``debug_transcript.py`` (``tee_stdio`` / ``progress``).

HTTP:
  ``POST …/map/pack/bake?mode=detailed&scope=location&location_uid=``
  ``POST …/map/pack/bake?mode=detailed&scope=wilderness&tile_gx=&tile_gy=``

Requires a running backend (``npm run backend``) — agents must not start it.

Examples:
  python backend/scripts/detailed_bake.py --world-uid world-test-003 \\
      --scope wilderness --gx -2 --gy -2
  python backend/scripts/detailed_bake.py --world-uid world-test-003 \\
      --scope wilderness --all-tiles --no-render
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

os.environ.setdefault("DEBUG_API_TIMEOUT", os.environ.get("DEBUG_API_TIMEOUT", "3600"))

from debug_api_helpers import (  # noqa: E402
    DebugApiError,
    api_client,
    api_list_locations,
    api_pack_bake,
)
from debug_surface_helpers import api_loading_progress  # noqa: E402
from debug_transcript import (  # noqa: E402
    add_debug_progress_argument,
    progress,
    set_debug_progress,
    tee_stdio,
)
from render_maps import _print_detailed_summary, dump_detailed_renders  # noqa: E402

_POLL_INTERVAL_S = float(os.environ.get("DETAILED_BAKE_POLL_S", "5"))


def _pack_dir(world_uid: str) -> Path:
    return REPO / "db" / "worlds" / world_uid / "pack"


def _report_dir(world_uid: str) -> Path:
    return REPO / ".local" / "map-render" / world_uid / "detailed-bake"


def _tile_dir(report_root: Path, gx: int, gy: int) -> Path:
    # Sign-safe folder name: gx-2_gy3
    return report_root / "tiles" / f"gx{gx}_gy{gy}"


def _location_dir(report_root: Path, location_uid: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in location_uid)
    return report_root / "locations" / safe


def _append_global_line(_global_log: Path, line: str) -> None:
    """Summary line → stdout; outer ``tee_stdio`` also writes ``detailed-bake-latest.log``."""
    print(line, flush=True)


def _format_tile_global_summary(
    *,
    gx: int,
    gy: int,
    cells: int,
    detail: str,
    elapsed_s: float,
    error: str | None = None,
) -> str:
    """Global log line: cells count, detail status, run length in seconds."""
    if error:
        return (
            f"tile=({gx},{gy}) cells={cells} detail={detail} "
            f"elapsed_s={elapsed_s:.2f} error={error}"
        )
    return (
        f"tile=({gx},{gy}) cells={cells} detail={detail} elapsed_s={elapsed_s:.2f}"
    )


def _format_location_global_summary(
    *,
    location_uid: str,
    cells: int,
    detail: str,
    elapsed_s: float,
    error: str | None = None,
) -> str:
    if error:
        return (
            f"location={location_uid} cells={cells} detail={detail} "
            f"elapsed_s={elapsed_s:.2f} error={error}"
        )
    return (
        f"location={location_uid} cells={cells} detail={detail} "
        f"elapsed_s={elapsed_s:.2f}"
    )


def _read_locations_index_uids(world_uid: str) -> list[str]:
    path = _pack_dir(world_uid) / "locations_index.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    locs = data.get("locations") or []
    return [
        str(p["location_uid"])
        for p in locs
        if isinstance(p, dict) and p.get("location_uid")
    ]


def _location_terrain_entries(world_uid: str) -> list[dict[str, Any]]:
    manifest = _pack_dir(world_uid) / "manifest.json"
    if not manifest.is_file():
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    entries = data.get("location_terrain_entries") or []
    return [e for e in entries if isinstance(e, dict)]


def _wilderness_tile_summary(world_uid: str) -> dict[str, Any]:
    manifest = _pack_dir(world_uid) / "manifest.json"
    if not manifest.is_file():
        return {"tiles": 0, "chunks": 0, "status_counts": {}}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    tiles = data.get("tiles") or []
    status_counts: dict[str, int] = {}
    chunks = 0
    for tile in tiles:
        if not isinstance(tile, dict):
            continue
        status = str(tile.get("wilderness_refine_status") or "absent")
        status_counts[status] = status_counts.get(status, 0) + 1
        chunks += len(tile.get("chunks") or [])
    return {
        "tiles": len(tiles),
        "chunks": chunks,
        "wilderness_chunks_baked": data.get("wilderness_chunks_baked"),
        "status_counts": status_counts,
    }


def _list_wilderness_cells(world_uid: str, *, include_complete: bool = False) -> list[tuple[int, int]]:
    manifest = _pack_dir(world_uid) / "manifest.json"
    if not manifest.is_file():
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    out: list[tuple[int, int]] = []
    for tile in data.get("tiles") or []:
        if not isinstance(tile, dict) or not tile.get("world_map_path"):
            continue
        if not include_complete and tile.get("wilderness_refine_status") == "complete":
            continue
        out.append((int(tile["gx"]), int(tile["gy"])))
    out.sort(key=lambda t: (t[1], t[0]))
    return out


def _cell_progress(world_uid: str, gx: int, gy: int) -> dict[str, Any]:
    manifest = _pack_dir(world_uid) / "manifest.json"
    if not manifest.is_file():
        return {"chunks": 0, "status": "absent"}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for tile in data.get("tiles") or []:
        if not isinstance(tile, dict):
            continue
        if int(tile.get("gx", 10**9)) == gx and int(tile.get("gy", 10**9)) == gy:
            return {
                "chunks": len(tile.get("chunks") or []),
                "status": tile.get("wilderness_refine_status") or "absent",
            }
    return {"chunks": 0, "status": "absent"}


@contextmanager
def _online_cell_progress(world_uid: str, gx: int, gy: int) -> Iterator[None]:
    stop = threading.Event()
    last: tuple[int, str] | None = None
    t0 = time.perf_counter()

    def _fmt_line(chunks: int, status: str, *, suffix: str = "") -> str:
        elapsed_s = time.perf_counter() - t0
        tail = f" {suffix}" if suffix else ""
        return (
            f"[online] cell=({gx},{gy}) chunks={chunks} status={status} "
            f"elapsed_s={elapsed_s:.2f}{tail}"
        )

    def _loop() -> None:
        nonlocal last
        while not stop.wait(_POLL_INTERVAL_S):
            prog = _cell_progress(world_uid, gx, gy)
            key = (int(prog["chunks"]), str(prog["status"]))
            if key == last:
                continue
            last = key
            progress(_fmt_line(key[0], key[1]))

    thread = threading.Thread(target=_loop, name=f"detailed-bake-poll-{gx}-{gy}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=_POLL_INTERVAL_S + 1.0)
        prog = _cell_progress(world_uid, gx, gy)
        progress(
            _fmt_line(int(prog["chunks"]), str(prog["status"]), suffix="(final poll)"),
        )


def _resolve_location_targets(
    client,
    world_uid: str,
    *,
    location_uid: str | None,
    all_locations: bool,
) -> list[str]:
    if location_uid and all_locations:
        raise SystemExit("use either --location-uid or --all, not both")
    if location_uid:
        return [location_uid]
    if not all_locations:
        raise SystemExit("scope=location requires --location-uid UID or --all")

    pins = _read_locations_index_uids(world_uid)
    if pins:
        print(f"targets from locations_index ({len(pins)}):")
        for uid in pins:
            print(f"  {uid}")
        return pins

    locs = api_list_locations(client, world_uid)
    uids = [
        str(loc["location_uid"])
        for loc in locs
        if loc.get("map_x") is not None and loc.get("map_y") is not None
    ]
    if not uids:
        raise SystemExit(
            f"no locations_index pins and no map_x/map_y locations for {world_uid}"
        )
    print(f"targets from GET locations with map coords ({len(uids)}):")
    for uid in uids:
        print(f"  {uid}")
    return uids


def _run_detailed_location(
    client,
    world_uid: str,
    location_uid: str,
    *,
    report_root: Path,
    global_log: Path,
    stamp: str,
) -> dict[str, Any]:
    loc_dir = _location_dir(report_root, location_uid)
    loc_dir.mkdir(parents=True, exist_ok=True)
    tile_log = loc_dir / "location-latest.log"
    stamped = loc_dir / f"location-{stamp}.log"

    started_at = datetime.now().astimezone()
    t0 = time.perf_counter()
    elapsed_s = 0.0
    error: str | None = None
    bake: dict[str, Any] = {}
    cells = 0
    detail = "absent"

    try:
        with tee_stdio(tile_log):
            print(f"=== detailed_bake location {location_uid} start ===", flush=True)
            bake = api_pack_bake(
                client,
                world_uid,
                mode="detailed",
                scope="location",
                location_uid=location_uid,
            )
            if not bake.get("loading_progress"):
                bake = {
                    **bake,
                    "loading_progress": api_loading_progress(client, world_uid),
                }
            terrain = bake.get("terrain") or {}
            cells = int(
                bake.get("wilderness_chunks")
                or terrain.get("succeeded")
                or bake.get("succeeded")
                or 0
            )
            detail = "ok" if not (bake.get("terrain_failed") or terrain.get("failed")) else "failed"
            elapsed_s = time.perf_counter() - t0
            print(f"=== detailed_bake location {location_uid} done ===", flush=True)
            print(f"elapsed_s={elapsed_s:.2f}", flush=True)
            for key in (
                "tiles_refined",
                "wilderness_chunks",
                "climate_fine_tiles",
                "succeeded",
                "failed",
            ):
                if key in bake or key in terrain:
                    print(f"  {key}={bake.get(key, terrain.get(key))}", flush=True)
    except DebugApiError as exc:
        error = str(exc)
        detail = "error"
        raise
    finally:
        elapsed_s = time.perf_counter() - t0
        if tile_log.is_file():
            stamped.write_text(tile_log.read_text(encoding="utf-8"), encoding="utf-8")
        summary_line = _format_location_global_summary(
            location_uid=location_uid,
            cells=cells,
            detail=detail,
            elapsed_s=elapsed_s,
            error=error,
        )
        _append_global_line(global_log, summary_line)
        (loc_dir / "summary.json").write_text(
            json.dumps(
                {
                    "location_uid": location_uid,
                    "cells": cells,
                    "detail": detail,
                    "elapsed_s": round(elapsed_s, 2),
                    "error": error,
                    "started_at": started_at.isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    terrain = bake.get("terrain") or {}
    return {
        "scope": "location",
        "location_uid": location_uid,
        "cells": cells,
        "detail": detail,
        "elapsed_s": round(elapsed_s, 2),
        "tile_log": str(tile_log),
        "terrain_succeeded": terrain.get("succeeded") or bake.get("succeeded"),
        "terrain_failed": terrain.get("failed") or bake.get("failed") or bake.get("terrain_failed"),
        "climate_fine_tiles": bake.get("climate_fine_tiles"),
    }


def _run_detailed_wilderness_cell(
    client,
    world_uid: str,
    gx: int,
    gy: int,
    *,
    report_root: Path,
    global_log: Path,
    stamp: str,
) -> dict[str, Any]:
    cell_dir = _tile_dir(report_root, gx, gy)
    cell_dir.mkdir(parents=True, exist_ok=True)
    tile_log = cell_dir / "tile-latest.log"
    stamped = cell_dir / f"tile-{stamp}.log"

    started_at = datetime.now().astimezone()
    t0 = time.perf_counter()
    elapsed_s = 0.0
    error: str | None = None
    bake: dict[str, Any] = {}
    before = _cell_progress(world_uid, gx, gy)
    after = before
    cells = 0
    detail = "absent"

    try:
        with tee_stdio(tile_log):
            print(f"=== detailed_bake wilderness cell=({gx},{gy}) start ===", flush=True)
            print(
                f"[online] cell=({gx},{gy}) chunks={before['chunks']} "
                f"status={before['status']} elapsed_s=0.00 (before)",
                flush=True,
            )
            with _online_cell_progress(world_uid, gx, gy):
                bake = api_pack_bake(
                    client,
                    world_uid,
                    mode="detailed",
                    scope="wilderness",
                    tile_gx=gx,
                    tile_gy=gy,
                )
            after = _cell_progress(world_uid, gx, gy)
            if not bake.get("loading_progress"):
                bake = {
                    **bake,
                    "loading_progress": api_loading_progress(client, world_uid),
                }
            cells = int(after["chunks"])
            detail = str(after["status"])
            elapsed_s = time.perf_counter() - t0
            print(f"=== detailed_bake wilderness cell=({gx},{gy}) done ===", flush=True)
            print(
                f"chunks_before={before['chunks']} chunks_after={after['chunks']} "
                f"detail={detail} elapsed_s={elapsed_s:.2f}",
                flush=True,
            )
    except DebugApiError as exc:
        error = str(exc)
        after = _cell_progress(world_uid, gx, gy)
        cells = int(after["chunks"])
        detail = str(after.get("status") or "error")
        raise
    finally:
        elapsed_s = time.perf_counter() - t0
        cells = int(after["chunks"])
        detail = str(after.get("status") or detail)
        if tile_log.is_file():
            stamped.write_text(tile_log.read_text(encoding="utf-8"), encoding="utf-8")
        summary_line = _format_tile_global_summary(
            gx=gx,
            gy=gy,
            cells=cells,
            detail=detail if not error else detail,
            elapsed_s=elapsed_s,
            error=error,
        )
        _append_global_line(global_log, summary_line)
        (cell_dir / "summary.json").write_text(
            json.dumps(
                {
                    "tile_gx": gx,
                    "tile_gy": gy,
                    "cells": cells,
                    "detail": detail,
                    "elapsed_s": round(elapsed_s, 2),
                    "chunks_before": before["chunks"],
                    "chunks_after": after["chunks"],
                    "error": error,
                    "started_at": started_at.isoformat(timespec="seconds"),
                    "tile_log": str(tile_log),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return {
        "scope": "wilderness",
        "cell_gx": gx,
        "cell_gy": gy,
        "cells": cells,
        "detail": detail,
        "elapsed_s": round(elapsed_s, 2),
        "chunks_before": before["chunks"],
        "chunks_after": after["chunks"],
        "tile_log": str(tile_log),
        "wilderness_chunks": bake.get("wilderness_chunks"),
        "tiles_refined": bake.get("tiles_refined"),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Smoke detailed_bake; per-tile logs + global summary log",
    )
    parser.add_argument("--world-uid", required=True, help="Existing world with L0 pack")
    parser.add_argument(
        "--scope",
        choices=("location", "wilderness"),
        required=True,
    )
    parser.add_argument("--location-uid", help="scope=location: single location")
    parser.add_argument("--all", action="store_true", help="scope=location: all pins")
    parser.add_argument("--gx", type=int, help="scope=wilderness: macro-tile gx")
    parser.add_argument("--gy", type=int, help="scope=wilderness: macro-tile gy")
    parser.add_argument(
        "--all-tiles",
        action="store_true",
        help="scope=wilderness: one HTTP job per incomplete macro-tile",
    )
    parser.add_argument(
        "--max-tiles",
        type=int,
        default=0,
        help="with --all-tiles: cap cells (0=all incomplete)",
    )
    parser.add_argument(
        "--render",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Dump L2 ASCII (location + wilderness mosaics) after bake (default: on)",
    )
    add_debug_progress_argument(parser)
    args = parser.parse_args()
    set_debug_progress(args.debug)

    if args.scope == "wilderness":
        if args.all_tiles and (args.gx is not None or args.gy is not None):
            raise SystemExit("use either --all-tiles or --gx/--gy, not both")
        if not args.all_tiles and (args.gx is None or args.gy is None):
            raise SystemExit(
                "scope=wilderness requires --gx N --gy M (one tile) or --all-tiles"
            )
        if (args.gx is None) ^ (args.gy is None):
            raise SystemExit("--gx and --gy must both be set")

    world_uid = args.world_uid
    report_root = _report_dir(world_uid)
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    global_log = report_root / "detailed-bake-latest.log"
    stamped_global = report_root / f"detailed-bake-{stamp}.log"

    # Entire run: terminal + detailed-bake-latest.log. Nested tile/location tee
    # keeps current stdout as primary → also lands in the global log.
    with tee_stdio(global_log):
        print(
            f"# detailed_bake global transcript  world={world_uid}  started={stamp}",
            flush=True,
        )
        print(f"report dir: {report_root}", flush=True)
        print(f"global log: {global_log}", flush=True)
        print(f"DEBUG_API_TIMEOUT={os.environ.get('DEBUG_API_TIMEOUT')}s", flush=True)

        with api_client() as client:
            if not (_pack_dir(world_uid) / "manifest.json").is_file():
                raise SystemExit(
                    f"no pack manifest for {world_uid} — run light_and_full_bake / full first"
                )

            before_loc = _location_terrain_entries(world_uid)
            before_wild = _wilderness_tile_summary(world_uid)
            print(f"location_terrain_entries before: {len(before_loc)}", flush=True)
            print(
                f"wilderness before: tiles={before_wild['tiles']} "
                f"chunks={before_wild['chunks']} status={before_wild['status_counts']}",
                flush=True,
            )

            results: list[dict[str, Any]] = []
            failures = 0
            targets: list[str] = []
            cells: list[tuple[int, int]] = []

            if args.scope == "wilderness":
                if args.all_tiles:
                    cells = _list_wilderness_cells(world_uid)
                    if args.max_tiles > 0:
                        cells = cells[: args.max_tiles]
                    print(f"wilderness tiles to bake ({len(cells)}):", flush=True)
                    for gx, gy in cells:
                        print(
                            f"  tile=({gx},{gy}) → {_tile_dir(report_root, gx, gy)}",
                            flush=True,
                        )
                else:
                    cells = [(int(args.gx), int(args.gy))]

                for gx, gy in cells:
                    try:
                        results.append(
                            _run_detailed_wilderness_cell(
                                client,
                                world_uid,
                                gx,
                                gy,
                                report_root=report_root,
                                global_log=global_log,
                                stamp=stamp,
                            )
                        )
                    except DebugApiError as exc:
                        failures += 1
                        print(f"FAIL detailed_bake tile=({gx},{gy}): {exc}", flush=True)
                        results.append({
                            "scope": "wilderness",
                            "cell_gx": gx,
                            "cell_gy": gy,
                            "error": str(exc),
                        })
            else:
                targets = _resolve_location_targets(
                    client,
                    world_uid,
                    location_uid=args.location_uid,
                    all_locations=args.all,
                )
                for uid in targets:
                    try:
                        results.append(
                            _run_detailed_location(
                                client,
                                world_uid,
                                uid,
                                report_root=report_root,
                                global_log=global_log,
                                stamp=stamp,
                            )
                        )
                    except DebugApiError as exc:
                        failures += 1
                        print(f"FAIL detailed_bake {uid}: {exc}", flush=True)
                        results.append({
                            "scope": "location",
                            "location_uid": uid,
                            "error": str(exc),
                        })

            after_loc = _location_terrain_entries(world_uid)
            after_wild = _wilderness_tile_summary(world_uid)
            print(f"location_terrain_entries after: {len(after_loc)}", flush=True)
            print(
                f"wilderness after: tiles={after_wild['tiles']} "
                f"chunks={after_wild['chunks']} status={after_wild['status_counts']}",
                flush=True,
            )

            report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "world_uid": world_uid,
                "scope": args.scope,
                "targets": targets,
                "cells": [{"gx": gx, "gy": gy} for gx, gy in cells],
                "results": results,
                "failures": failures,
                "global_log": str(global_log),
                "location_terrain_before": before_loc,
                "location_terrain_after": after_loc,
                "wilderness_before": before_wild,
                "wilderness_after": after_wild,
            }
            json_latest = report_root / "detailed-bake-latest.json"
            json_stamped = report_root / f"detailed-bake-{stamp}.json"
            payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            json_latest.write_text(payload, encoding="utf-8")
            json_stamped.write_text(payload, encoding="utf-8")
            print(f"JSON report: {json_latest}", flush=True)

            if args.render:
                print("=== detailed L2 render after detailed_bake ===", flush=True)
                wild_tiles = list(cells) if args.scope == "wilderness" else []
                loc_uids = list(targets) if args.scope == "location" else []
                summary = dump_detailed_renders(
                    client,
                    world_uid,
                    out_root=report_root / "after-detailed",
                    wilderness_tiles=wild_tiles,
                    location_uids=loc_uids,
                )
                _print_detailed_summary(summary)
                report["render"] = summary
                payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                json_latest.write_text(payload, encoding="utf-8")
                json_stamped.write_text(payload, encoding="utf-8")

    # Copy after tee closes so the file is fully flushed/closed.
    stamped_global.write_text(global_log.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"stamped global log: {stamped_global}", flush=True)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
