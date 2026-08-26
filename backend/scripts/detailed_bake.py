"""Smoke: detailed_bake L2 — location territory and/or wilderness tiles.

Assumes the world already has L0 parent light (after light_and_full_bake / full).
Does **not** wipe pack, re-import, or run entry/bg refine.

**Logs:** ``backend/logs/script/detailedBake.log`` + console JSON,
``backend/logs/render/dumpLog.log`` (ASCII dump), and
``backend/logs/generation/{uid}/bake-dump-*.log`` (``generation_world_log(mode="dump")``).
ASCII artifacts stay under ``.local/map-render/``. Heartbeat ≤5 s via ``dumpLog``.

HTTP:
  ``POST …/map/pack/bake?mode=detailed&scope=location&location_uid=``
  ``POST …/map/pack/bake?mode=detailed&scope=wilderness&tile_gx=&tile_gy=``

Requires a running backend (``npm run backend``) — agents must not start it.

Examples:
  python backend/scripts/detailed_bake.py --world-uid world-test-003 \\
      --scope wilderness --gx -2 --gy -2
  python backend/scripts/detailed_bake.py --world-uid world-test-003 \\
      --scope wilderness --gx -2 --gy -2 --z-range 920:930
  python backend/scripts/detailed_bake.py --world-uid world-test-003 \\
      --scope wilderness --gx -2 --gy -2 --grade-z --z-range 920:930
  python backend/scripts/detailed_bake.py --world-uid world-test-003 \\
      --scope wilderness --all-tiles --no-render
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from app.application.worldData.render.dumpLog import (  # noqa: E402
    add_debug_logging_argument,
    heartbeat_loop,
    log_dump,
    log_dump_warning,
)
from app.application.worldData.generators.terrain.relief.discover.timings import (  # noqa: E402
    GradePipelineTimings,
)
from app.core.generationLogging import generation_world_log  # noqa: E402
from app.core.loggingConfig import ensure_script_logging  # noqa: E402
from render_maps import (  # noqa: E402
    _print_detailed_summary,
    argparse_z_range,
    dump_detailed_renders,
)

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


_BAKE_ONLY_KEYS = ("grade_persist_s", "l2_s")
_PIPELINE_KEYS = GradePipelineTimings.wire_keys() + _BAKE_ONLY_KEYS


def _grade_pipeline_from_bake(bake: dict[str, Any]) -> dict[str, float]:
    raw = bake.get("grade_pipeline")
    src = raw if isinstance(raw, dict) else bake
    out: dict[str, float] = {}
    for key in _PIPELINE_KEYS:
        val = src.get(key, bake.get(key))
        if val is None:
            continue
        try:
            out[key] = round(float(val), 3)
        except (TypeError, ValueError):
            continue
    return out


def _log_grade_pipeline(bake: dict[str, Any], *, activity: str) -> dict[str, float]:
    pipeline = _grade_pipeline_from_bake(bake)
    if not pipeline:
        log_dump("grade pipeline timings absent from bake response", activity=activity)
        return pipeline
    parts = " ".join(f"{key}={value:.2f}" for key, value in pipeline.items())
    log_dump(
        "grade pipeline "
        f"{parts} (q/mill/paint/grade/materialize are CPU-sum over chunks; l2_s is wall)",
        activity=activity,
        **pipeline,
    )
    return pipeline


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
        log_dump(
            f"targets from locations_index ({len(pins)})",
            activity="detailed_bake",
        )
        for uid in pins:
            log_dump(f"  {uid}", activity="detailed_bake")
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
    log_dump(
        f"targets from GET locations with map coords ({len(uids)})",
        activity="detailed_bake",
    )
    for uid in uids:
        log_dump(f"  {uid}", activity="detailed_bake")
    return uids


def _run_detailed_location(
    client,
    world_uid: str,
    location_uid: str,
    *,
    report_root: Path,
) -> dict[str, Any]:
    loc_dir = _location_dir(report_root, location_uid)
    loc_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now().astimezone()
    t0 = time.perf_counter()
    elapsed_s = 0.0
    error: str | None = None
    bake: dict[str, Any] = {}
    cells = 0
    detail = "absent"
    pipeline: dict[str, float] = {}

    try:
        log_dump(
            f"detailed_bake location {location_uid} start",
            activity="detailed_bake",
            location_uid=location_uid,
        )
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
        log_dump(
            f"detailed_bake location {location_uid} done elapsed_s={elapsed_s:.2f}",
            activity="detailed_bake",
            location_uid=location_uid,
            elapsed_s=round(elapsed_s, 2),
        )
        pipeline = _log_grade_pipeline(bake, activity="detailed_bake")
        for key in (
            "tiles_refined",
            "wilderness_chunks",
            "climate_fine_tiles",
            "succeeded",
            "failed",
        ):
            if key in bake or key in terrain:
                log_dump(
                    f"  {key}={bake.get(key, terrain.get(key))}",
                    activity="detailed_bake",
                )
    except DebugApiError as exc:
        error = str(exc)
        detail = "error"
        raise
    finally:
        elapsed_s = time.perf_counter() - t0
        summary_line = _format_location_global_summary(
            location_uid=location_uid,
            cells=cells,
            detail=detail,
            elapsed_s=elapsed_s,
            error=error,
        )
        log_dump(summary_line, activity="detailed_bake")
        (loc_dir / "summary.json").write_text(
            json.dumps(
                {
                    "location_uid": location_uid,
                    "cells": cells,
                    "detail": detail,
                    "elapsed_s": round(elapsed_s, 2),
                    "error": error,
                    "started_at": started_at.isoformat(timespec="seconds"),
                    "grade_pipeline": pipeline,
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
        "terrain_succeeded": terrain.get("succeeded") or bake.get("succeeded"),
        "terrain_failed": terrain.get("failed") or bake.get("failed") or bake.get("terrain_failed"),
        "climate_fine_tiles": bake.get("climate_fine_tiles"),
        "grade_pipeline": pipeline,
    }


def _run_detailed_wilderness_cell(
    client,
    world_uid: str,
    gx: int,
    gy: int,
    *,
    report_root: Path,
) -> dict[str, Any]:
    cell_dir = _tile_dir(report_root, gx, gy)
    cell_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now().astimezone()
    t0 = time.perf_counter()
    elapsed_s = 0.0
    error: str | None = None
    bake: dict[str, Any] = {}
    before = _cell_progress(world_uid, gx, gy)
    after = before
    cells = 0
    detail = "absent"
    pipeline: dict[str, float] = {}

    def _poll_line() -> str:
        prog = _cell_progress(world_uid, gx, gy)
        elapsed = time.perf_counter() - t0
        return (
            f"[online] cell=({gx},{gy}) chunks={prog['chunks']} "
            f"status={prog['status']} elapsed_s={elapsed:.2f}"
        )

    try:
        log_dump(
            f"detailed_bake wilderness cell=({gx},{gy}) start",
            activity="detailed_bake",
            tile_gx=gx,
            tile_gy=gy,
        )
        log_dump(
            f"[online] cell=({gx},{gy}) chunks={before['chunks']} "
            f"status={before['status']} elapsed_s=0.00 (before)",
            activity="detailed_bake_poll",
            tile_gx=gx,
            tile_gy=gy,
        )
        with heartbeat_loop(
            _poll_line,
            interval_s=_POLL_INTERVAL_S,
            activity="detailed_bake_poll",
        ):
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
        log_dump(
            f"detailed_bake wilderness cell=({gx},{gy}) done "
            f"chunks_before={before['chunks']} chunks_after={after['chunks']} "
            f"detail={detail} elapsed_s={elapsed_s:.2f}",
            activity="detailed_bake",
            tile_gx=gx,
            tile_gy=gy,
            elapsed_s=round(elapsed_s, 2),
        )
        pipeline = _log_grade_pipeline(bake, activity="detailed_bake")
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
        summary_line = _format_tile_global_summary(
            gx=gx,
            gy=gy,
            cells=cells,
            detail=detail if not error else detail,
            elapsed_s=elapsed_s,
            error=error,
        )
        log_dump(summary_line, activity="detailed_bake")
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
                    "grade_pipeline": pipeline,
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
        "wilderness_chunks": bake.get("wilderness_chunks"),
        "tiles_refined": bake.get("tiles_refined"),
        "grade_pipeline": pipeline,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Smoke detailed_bake; JSON reports under .local, logs via app logger",
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
    parser.add_argument(
        "--grade-z",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Also dump z/grade_<n>.txt per surface-z (slow; default: off). "
        "surface_grade.txt is always written when --render is on",
    )
    parser.add_argument(
        "--z-range",
        type=argparse_z_range,
        default=None,
        metavar="N[:M]",
        help="Dump only world-z N or N:M inclusive (colon, negatives ok: "
        "--z-range=-5:10). Applies to z/*.txt and --grade-z files. "
        "Default: all occupied z. surface / surface_z / surface_grade stay full-tile",
    )
    add_debug_logging_argument(parser)
    args = parser.parse_args()
    ensure_script_logging(service="detailedBake", debug=args.debug)

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
    failures = 0

    with generation_world_log(world_uid, mode="dump") as gen_log:
        log_dump(
            f"detailed_bake start world={world_uid} started={stamp}",
            activity="detailed_bake",
            world_uid=world_uid,
        )
        log_dump(f"report dir: {report_root}", activity="detailed_bake")
        log_dump(f"generation log: {gen_log}", activity="detailed_bake")
        log_dump(
            f"DEBUG_API_TIMEOUT={os.environ.get('DEBUG_API_TIMEOUT')}s",
            activity="detailed_bake",
        )

        with api_client() as client:
            if not (_pack_dir(world_uid) / "manifest.json").is_file():
                raise SystemExit(
                    f"no pack manifest for {world_uid} — run light_and_full_bake / full first"
                )

            before_loc = _location_terrain_entries(world_uid)
            before_wild = _wilderness_tile_summary(world_uid)
            log_dump(
                f"location_terrain_entries before: {len(before_loc)}",
                activity="detailed_bake",
            )
            log_dump(
                f"wilderness before: tiles={before_wild['tiles']} "
                f"chunks={before_wild['chunks']} status={before_wild['status_counts']}",
                activity="detailed_bake",
            )

            results: list[dict[str, Any]] = []
            targets: list[str] = []
            cells: list[tuple[int, int]] = []

            if args.scope == "wilderness":
                if args.all_tiles:
                    cells = _list_wilderness_cells(world_uid)
                    if args.max_tiles > 0:
                        cells = cells[: args.max_tiles]
                    log_dump(
                        f"wilderness tiles to bake ({len(cells)})",
                        activity="detailed_bake",
                    )
                    for gx, gy in cells:
                        log_dump(
                            f"  tile=({gx},{gy}) → {_tile_dir(report_root, gx, gy)}",
                            activity="detailed_bake",
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
                            )
                        )
                    except DebugApiError as exc:
                        failures += 1
                        log_dump_warning(
                            f"FAIL detailed_bake tile=({gx},{gy}): {exc}",
                            activity="detailed_bake",
                        )
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
                            )
                        )
                    except DebugApiError as exc:
                        failures += 1
                        log_dump_warning(
                            f"FAIL detailed_bake {uid}: {exc}",
                            activity="detailed_bake",
                        )
                        results.append({
                            "scope": "location",
                            "location_uid": uid,
                            "error": str(exc),
                        })

            after_loc = _location_terrain_entries(world_uid)
            after_wild = _wilderness_tile_summary(world_uid)
            log_dump(
                f"location_terrain_entries after: {len(after_loc)}",
                activity="detailed_bake",
            )
            log_dump(
                f"wilderness after: tiles={after_wild['tiles']} "
                f"chunks={after_wild['chunks']} status={after_wild['status_counts']}",
                activity="detailed_bake",
            )

            report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "world_uid": world_uid,
                "scope": args.scope,
                "targets": targets,
                "cells": [{"gx": gx, "gy": gy} for gx, gy in cells],
                "results": results,
                "failures": failures,
                "generation_log": str(gen_log),
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
            log_dump(f"JSON report: {json_latest}", activity="detailed_bake")

            if args.render:
                log_dump(
                    "detailed L2 render after detailed_bake",
                    activity="detailed_bake",
                )
                wild_tiles = list(cells) if args.scope == "wilderness" else []
                loc_uids = list(targets) if args.scope == "location" else []
                z_min, z_max = args.z_range if args.z_range is not None else (None, None)
                summary = dump_detailed_renders(
                    client,
                    world_uid,
                    out_root=report_root / "after-detailed",
                    wilderness_tiles=wild_tiles,
                    location_uids=loc_uids,
                    write_grade_z_files=args.grade_z,
                    z_min=z_min,
                    z_max=z_max,
                )
                _print_detailed_summary(summary)
                report["render"] = summary
                payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                json_latest.write_text(payload, encoding="utf-8")
                json_stamped.write_text(payload, encoding="utf-8")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
