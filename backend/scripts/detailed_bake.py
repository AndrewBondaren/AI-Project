"""Smoke: detailed_bake L2 — location territory and/or wilderness tiles.

Assumes the world already has L0 parent light (after light_and_full_bake / full).
Does **not** wipe pack, re-import, or run entry/bg refine.

HTTP:
  ``POST …/map/pack/bake?mode=detailed&scope=location&location_uid=``
  ``POST …/map/pack/bake?mode=detailed&scope=wilderness``

Reports + renders → ``.local/map-render/{uid}/detailed-bake/``

Requires a running backend (``npm run backend``) — agents must not start it.

Examples:
  python backend/scripts/detailed_bake.py --world-uid world-test-003 --scope wilderness
  python backend/scripts/detailed_bake.py --world-uid world-test-002 --scope location --all
  python backend/scripts/detailed_bake.py --world-uid world-test-002 \\
      --scope location --location-uid loc-city-ironhold-002
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, TextIO

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from debug_api_helpers import (
    DebugApiError,
    api_client,
    api_list_locations,
    api_pack_bake,
)
from debug_surface_helpers import api_loading_progress
from render_maps import _print_summary, dump_map_renders

_DEFAULT_TIMEOUT_S = float(os.environ.get("DEBUG_API_TIMEOUT", "600"))


class _TeeStream:
    def __init__(self, primary: TextIO, log_file: TextIO) -> None:
        self._primary = primary
        self._log = log_file

    def write(self, data: str) -> int:
        self._primary.write(data)
        self._log.write(data)
        return len(data)

    def flush(self) -> None:
        self._primary.flush()
        self._log.flush()

    def reconfigure(self, **kwargs: Any) -> None:  # noqa: ANN401
        reconf = getattr(self._primary, "reconfigure", None)
        if callable(reconf):
            reconf(**kwargs)


@contextmanager
def _tee_stdio(log_path: Path) -> Iterator[Path]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8", newline="\n")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = _TeeStream(old_out, log_file)  # type: ignore[assignment]
    sys.stderr = _TeeStream(old_err, log_file)  # type: ignore[assignment]
    try:
        yield log_path
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
        log_file.flush()
        log_file.close()
        print(f"\nfull transcript saved: {log_path}", file=old_out, flush=True)


def _pack_dir(world_uid: str) -> Path:
    return REPO / "db" / "worlds" / world_uid / "pack"


def _report_dir(world_uid: str) -> Path:
    return REPO / ".local" / "map-render" / world_uid / "detailed-bake"


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
) -> dict[str, Any]:
    started_at = datetime.now().astimezone()
    t0 = time.perf_counter()
    bake = api_pack_bake(
        client,
        world_uid,
        mode="detailed",
        scope="location",
        location_uid=location_uid,
    )
    http_elapsed_s = time.perf_counter() - t0
    finished_at = datetime.now().astimezone()
    if not bake.get("loading_progress"):
        bake = {**bake, "loading_progress": api_loading_progress(client, world_uid)}

    terrain = bake.get("terrain") or {}
    metrics = {
        "scope": bake.get("scope") or "location",
        "location_uid": location_uid,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "http_elapsed_s": round(http_elapsed_s, 2),
        "pack_mode": bake.get("pack_mode"),
        "tiles_refined": bake.get("tiles_refined"),
        "wilderness_chunks": bake.get("wilderness_chunks"),
        "terrain_succeeded": terrain.get("succeeded") or bake.get("succeeded"),
        "terrain_failed": terrain.get("failed") or bake.get("failed") or bake.get("terrain_failed"),
        "climate_fine_tiles": bake.get("climate_fine_tiles"),
        "elapsed_s": bake.get("elapsed_s"),
    }
    print(f"\n=== detailed_bake location {location_uid} ===")
    width = max(len(k) for k in metrics)
    for key, value in metrics.items():
        print(f"{key:<{width}}  {value}")
    return metrics


def _run_detailed_wilderness(
    client,
    world_uid: str,
    *,
    max_tiles: int,
) -> dict[str, Any]:
    started_at = datetime.now().astimezone()
    t0 = time.perf_counter()
    bake = api_pack_bake(
        client,
        world_uid,
        mode="detailed",
        scope="wilderness",
        max_tiles=max_tiles if max_tiles > 0 else None,
    )
    http_elapsed_s = time.perf_counter() - t0
    finished_at = datetime.now().astimezone()
    if not bake.get("loading_progress"):
        bake = {**bake, "loading_progress": api_loading_progress(client, world_uid)}

    terrain = bake.get("terrain") or {}
    metrics = {
        "scope": bake.get("scope") or "wilderness",
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "http_elapsed_s": round(http_elapsed_s, 2),
        "pack_mode": bake.get("pack_mode"),
        "tiles_refined": bake.get("tiles_refined"),
        "wilderness_chunks": bake.get("wilderness_chunks"),
        "terrain_succeeded": terrain.get("succeeded") or bake.get("succeeded"),
        "terrain_failed": terrain.get("failed") or bake.get("failed") or bake.get("terrain_failed"),
        "climate_fine_tiles": bake.get("climate_fine_tiles"),
        "elapsed_s": bake.get("elapsed_s"),
        "max_tiles": max_tiles or None,
    }
    print("\n=== detailed_bake wilderness ===")
    width = max(len(k) for k in metrics)
    for key, value in metrics.items():
        print(f"{key:<{width}}  {value}")
    return metrics


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ.setdefault("DEBUG_API_TIMEOUT", str(int(_DEFAULT_TIMEOUT_S)))

    parser = argparse.ArgumentParser(
        description="Smoke detailed_bake (scope=location|wilderness)",
    )
    parser.add_argument("--world-uid", required=True, help="Existing world with L0 pack")
    parser.add_argument(
        "--scope",
        choices=("location", "wilderness"),
        required=True,
        help="Detailed L2 scope (SoT; not inferred from missing uid)",
    )
    parser.add_argument("--location-uid", help="scope=location: single location")
    parser.add_argument(
        "--all",
        action="store_true",
        help="scope=location: each locations_index pin (fallback: map_x/map_y)",
    )
    parser.add_argument(
        "--max-tiles",
        type=int,
        default=0,
        help="scope=wilderness: debug tile cap (0=all L0 tiles with world_map)",
    )
    parser.add_argument(
        "--render",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Dump L0+L2 ASCII after bake (default: on)",
    )
    parser.add_argument(
        "--mark-locations",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()

    world_uid = args.world_uid
    report_root = _report_dir(world_uid)
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    transcript = report_root / "detailed-bake-latest.log"
    stamped_log = report_root / f"detailed-bake-{stamp}.log"

    print(f"report dir: {report_root}")
    print(f"transcript: {transcript}")

    with _tee_stdio(transcript), api_client() as client:
        if not (_pack_dir(world_uid) / "manifest.json").is_file():
            raise SystemExit(
                f"no pack manifest for {world_uid} — run light_and_full_bake / full first"
            )

        before_loc = _location_terrain_entries(world_uid)
        before_wild = _wilderness_tile_summary(world_uid)
        print(f"\nlocation_terrain_entries before: {len(before_loc)}")
        print(
            f"wilderness before: tiles={before_wild['tiles']} "
            f"chunks={before_wild['chunks']} status={before_wild['status_counts']}"
        )

        results: list[dict[str, Any]] = []
        failures = 0
        targets: list[str] = []

        if args.scope == "wilderness":
            try:
                results.append(
                    _run_detailed_wilderness(
                        client, world_uid, max_tiles=args.max_tiles,
                    )
                )
            except DebugApiError as exc:
                failures += 1
                print(f"FAIL detailed_bake wilderness: {exc}")
                results.append({"scope": "wilderness", "error": str(exc)})
        else:
            targets = _resolve_location_targets(
                client,
                world_uid,
                location_uid=args.location_uid,
                all_locations=args.all,
            )
            for uid in targets:
                try:
                    results.append(_run_detailed_location(client, world_uid, uid))
                except DebugApiError as exc:
                    failures += 1
                    print(f"FAIL detailed_bake {uid}: {exc}")
                    results.append({
                        "scope": "location",
                        "location_uid": uid,
                        "error": str(exc),
                    })

        after_loc = _location_terrain_entries(world_uid)
        after_wild = _wilderness_tile_summary(world_uid)
        print(f"\nlocation_terrain_entries after: {len(after_loc)}")
        for entry in after_loc:
            print(
                f"  {entry.get('location_uid')}  "
                f"path={entry.get('terrain_path')}  "
                f"hash={str(entry.get('terrain_hash') or '')[:12]}"
            )
        print(
            f"wilderness after: tiles={after_wild['tiles']} "
            f"chunks={after_wild['chunks']} status={after_wild['status_counts']}"
        )

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "world_uid": world_uid,
            "scope": args.scope,
            "targets": targets,
            "results": results,
            "failures": failures,
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
        print(f"\nJSON report: {json_latest}")

        if args.render:
            print("\n=== map render after detailed_bake ===")
            summary = dump_map_renders(
                client,
                world_uid,
                out_root=report_root / "after-detailed",
                mark_locations=args.mark_locations,
            )
            _print_summary(summary)
            report["render"] = summary
            payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            json_latest.write_text(payload, encoding="utf-8")
            json_stamped.write_text(payload, encoding="utf-8")

        stamped_log.write_text(transcript.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"stamped transcript: {stamped_log}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
