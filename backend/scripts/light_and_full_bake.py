"""Smoke: light_bake → full_bake on **one** world (same generation).

Unlike ``initialize_world.py`` (single mode), this script:
1. deletes the fixture world_uid (avoids import remap → new UUID world)
2. imports once
3. runs ``mode=light``, then ``mode=full`` without re-import
4. writes **full transcript + JSON report** under ``.local/map-render/…``
   (terminal also mirrors, but disk is the source of truth — buffers truncate)

Requires a running backend (``npm run backend``) — agents must not start it.

Examples:
  python backend/scripts/light_and_full_bake.py --fixture fixtures/world_test_gen.json
  python backend/scripts/light_and_full_bake.py --reuse --world-uid world-test-002

Artifacts (default):
  .local/map-render/{world_uid}/light-and-full/light-and-full-latest.log
  .local/map-render/{world_uid}/light-and-full/light-and-full-latest.json
  .local/map-render/{world_uid}/light-and-full/light-and-full-{UTC}.log|.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, TextIO

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from app.application.worldData.pack.import_.importLevels import filter_bundle_for_export
from debug_api_helpers import DebugApiError, _require_ok, api_clear_map, api_client, api_delete_world
from debug_surface_helpers import (
    api_list_bootstrap_tiles,
    api_loading_progress,
    api_pack_bake,
)
from render_maps import _print_summary, dump_map_renders

# Full bake can exceed the default 120s debug timeout.
_DEFAULT_TIMEOUT_S = float(os.environ.get("DEBUG_API_TIMEOUT", "600"))

TileKey = tuple[int, int]


class _TeeStream:
    """Mirror writes to terminal and a log file."""

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
        # Always tell the real terminal where the full transcript lives.
        print(f"\nfull transcript saved: {log_path}", file=old_out, flush=True)


def _tile_labels(tiles: set[TileKey] | list[TileKey]) -> list[str]:
    return [_tile_label(gx, gy) for gx, gy in _sorted_tiles(tiles)]


def _snap_for_json(snap: dict[str, Any]) -> dict[str, Any]:
    tiles = set(snap.get("tiles") or ())
    return {
        "bake_mode": snap.get("bake_mode"),
        "has_climate_coarse": snap.get("has_climate_coarse"),
        "has_locations_index": snap.get("has_locations_index"),
        "world_map_cells": snap.get("world_map_cells"),
        "manifest_path": snap.get("manifest_path"),
        "tile_count": len(tiles),
        "tiles": _tile_labels(tiles),
        "tile_blobs": snap.get("tile_blobs") or [],
    }


def _write_report_json(
    path: Path,
    *,
    world_uid: str,
    fixture: str,
    planned_light: set[TileKey],
    planned_full: set[TileKey],
    after_light: dict[str, Any],
    after_full: dict[str, Any],
) -> None:
    light_tiles: set[TileKey] = set(after_light.get("tiles") or ())
    full_tiles: set[TileKey] = set(after_full.get("tiles") or ())
    added = full_tiles - light_tiles
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "world_uid": world_uid,
        "fixture": fixture,
        "pack_dir": str(_pack_dir(world_uid)),
        "plan": {
            "light_tiles": _tile_labels(planned_light),
            "full_tiles": _tile_labels(planned_full),
            "full_minus_light": _tile_labels(planned_full - planned_light),
            "light_count": len(planned_light),
            "full_count": len(planned_full),
        },
        "after_light_bake": _snap_for_json(after_light),
        "after_full_bake": _snap_for_json(after_full),
        "delta": {
            "created_on_light": _tile_labels(light_tiles),
            "added_on_full": _tile_labels(added),
            "present_after_full": _tile_labels(full_tiles),
            "light_count": len(light_tiles),
            "added_count": len(added),
            "full_count": len(full_tiles),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def _loading_world_map(progress: dict) -> dict[str, Any]:
    wm = progress.get("worldMapLoading") or progress.get("world_map") or {}
    return wm if isinstance(wm, dict) else {}


def _tile_label(gx: int, gy: int) -> str:
    return f"Gx{gx}_Gy{gy}"


def _sorted_tiles(tiles: set[TileKey] | list[TileKey]) -> list[TileKey]:
    return sorted(tiles, key=lambda t: (t[1], t[0]))


def _print_tile_list(title: str, tiles: set[TileKey] | list[TileKey]) -> None:
    ordered = _sorted_tiles(tiles)
    print(f"{title} ({len(ordered)}):")
    if not ordered:
        print("  (none)")
        return
    for gx, gy in ordered:
        print(f"  {_tile_label(gx, gy)}")


def _tiles_from_plan(plan: dict) -> set[TileKey]:
    out: set[TileKey] = set()
    for tile in plan.get("tiles") or []:
        out.add((int(tile["gx"]), int(tile["gy"])))
    return out


def _pack_dir(world_uid: str) -> Path:
    return REPO / "db" / "worlds" / world_uid / "pack"


def _snapshot_pack(world_uid: str) -> dict[str, Any]:
    """Inventory of on-disk pack after a bake stage."""
    pack = _pack_dir(world_uid)
    manifest_path = pack / "manifest.json"
    if not manifest_path.is_file():
        return {
            "bake_mode": None,
            "tiles": set(),
            "tile_blobs": [],
            "has_climate_coarse": False,
            "has_locations_index": False,
            "manifest_path": str(manifest_path),
        }

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    tiles: set[TileKey] = set()
    tile_blobs: list[dict[str, Any]] = []
    for entry in data.get("tiles") or []:
        gx = int(entry["gx"])
        gy = int(entry["gy"])
        tiles.add((gx, gy))
        rel = entry.get("world_map_path")
        blob = (pack / rel) if rel else (pack / "tiles" / f"r.{gx}.{gy}.world_map.zst")
        tile_blobs.append({
            "gx": gx,
            "gy": gy,
            "label": _tile_label(gx, gy),
            "world_map_path": rel,
            "blob_exists": blob.is_file(),
            "blob_bytes": blob.stat().st_size if blob.is_file() else 0,
        })
    tile_blobs.sort(key=lambda b: (b["gy"], b["gx"]))
    return {
        "bake_mode": data.get("bake_mode"),
        "tiles": tiles,
        "tile_blobs": tile_blobs,
        "has_climate_coarse": (pack / "climate_coarse.zst").is_file(),
        "has_locations_index": (pack / "locations_index.json").is_file(),
        "world_map_cells": data.get("world_map_cells"),
        "manifest_path": str(manifest_path),
    }


def _print_stage_inventory(stage: str, snap: dict[str, Any]) -> None:
    print(f"\n=== CREATED ON {stage} (disk inventory) ===")
    print(f"manifest bake_mode     {snap.get('bake_mode')}")
    print(f"climate_coarse.zst     {snap.get('has_climate_coarse')}")
    print(f"locations_index.json   {snap.get('has_locations_index')}")
    print(f"world_map_cells        {snap.get('world_map_cells')}")
    print(f"L0 macro-tiles         {len(snap.get('tiles') or ())}")
    for blob in snap.get("tile_blobs") or []:
        status = "ok" if blob["blob_exists"] else "MISSING"
        print(
            f"  {blob['label']:<12}  {status:<7}  "
            f"{blob['blob_bytes']:>8} B  {blob.get('world_map_path') or '-'}"
        )


def _bake_metrics(
    bake: dict,
    *,
    started_at: datetime,
    finished_at: datetime,
    http_elapsed_s: float,
) -> dict[str, Any]:
    progress = bake.get("loading_progress") or {}
    wm = _loading_world_map(progress)
    completeness = progress.get("pack_completeness") or {}
    server_s = bake.get("elapsed_s")
    return {
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "http_elapsed_s": round(http_elapsed_s, 2),
        "server_bake_elapsed_s": round(server_s, 2) if server_s is not None else None,
        "pack_mode": bake.get("pack_mode"),
        "tiles_ready": wm.get("tiles_ready"),
        "tiles_total": wm.get("tiles_total"),
        "tiles_pct": wm.get("tiles_pct"),
        "l0_baked": completeness.get("l0_baked"),
        "expected_l0_light": completeness.get("expected_l0_light"),
        "expected_l0_full": completeness.get("expected_l0_full"),
        "world_map_cells": bake.get("world_map_cells"),
        "has_climate_coarse": progress.get("has_climate_coarse"),
    }


def _print_metrics(title: str, metrics: dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    width = max(len(str(k)) for k in metrics)
    for key, value in metrics.items():
        print(f"{key:<{width}}  {value}")


def _run_bake(
    client,
    world_uid: str,
    *,
    mode: str,
    max_tiles: int | None,
) -> dict[str, Any]:
    started_at = datetime.now().astimezone()
    t0 = time.perf_counter()
    bake = api_pack_bake(
        client,
        world_uid,
        mode=mode,  # type: ignore[arg-type]
        max_tiles=max_tiles if mode == "light" else None,
    )
    http_elapsed_s = time.perf_counter() - t0
    finished_at = datetime.now().astimezone()
    if not bake.get("loading_progress"):
        bake = {**bake, "loading_progress": api_loading_progress(client, world_uid)}
    metrics = _bake_metrics(
        bake,
        started_at=started_at,
        finished_at=finished_at,
        http_elapsed_s=http_elapsed_s,
    )
    _print_metrics(f"{mode}_bake metrics", metrics)
    return metrics


def _wipe_local_pack(world_uid: str) -> None:
    """Best-effort wipe of on-disk pack so light→full starts clean."""
    pack_root = REPO / "db" / "worlds" / world_uid
    if pack_root.is_dir():
        shutil.rmtree(pack_root, ignore_errors=True)
        print(f"wiped local pack dir: {pack_root}")


def _print_delta_report(
    *,
    world_uid: str,
    planned_light: set[TileKey],
    planned_full: set[TileKey],
    after_light: dict[str, Any],
    after_full: dict[str, Any],
) -> None:
    light_tiles: set[TileKey] = set(after_light.get("tiles") or ())
    full_tiles: set[TileKey] = set(after_full.get("tiles") or ())
    added = full_tiles - light_tiles
    removed = light_tiles - full_tiles  # should be empty
    planned_full_only = planned_full - planned_light

    print("\n" + "=" * 60)
    print("LIGHT_BAKE vs FULL_BAKE — what was created")
    print("=" * 60)
    print(f"world_uid: {world_uid}")
    print(f"pack dir:  {_pack_dir(world_uid)}")

    print("\n--- PLAN (before bake) ---")
    _print_tile_list("planned light_bake tiles", planned_light)
    _print_tile_list("planned full_bake tiles", planned_full)
    _print_tile_list("planned only on full (delta)", planned_full_only)

    print("\n--- AFTER light_bake (on disk) ---")
    print(f"bake_mode:           {after_light.get('bake_mode')}")
    print(f"climate_coarse:      {after_light.get('has_climate_coarse')}")
    print(f"locations_index:     {after_light.get('has_locations_index')}")
    _print_tile_list("L0 tiles created by light_bake", light_tiles)

    print("\n--- AFTER full_bake (on disk) ---")
    print(f"bake_mode:           {after_full.get('bake_mode')}")
    print(f"climate_coarse:      {after_full.get('has_climate_coarse')}")
    print(f"locations_index:     {after_full.get('has_locations_index')}")
    _print_tile_list("L0 tiles present after full_bake", full_tiles)
    _print_tile_list("L0 tiles ADDED by full_bake", added)
    if removed:
        _print_tile_list("L0 tiles lost after full (unexpected)", removed)

    print("\n--- SUMMARY ---")
    print(f"light_bake created:  {len(light_tiles)} tile(s)")
    print(f"full_bake added:     {len(added)} tile(s)")
    print(f"full_bake total:     {len(full_tiles)} tile(s)")
    if light_tiles and not light_tiles <= full_tiles:
        print("WARNING: some light tiles missing after full — check bake/overwrite")
    if planned_light and light_tiles != planned_light:
        print(
            f"NOTE: light disk tiles ({len(light_tiles)}) != planned light "
            f"({len(planned_light)})"
        )
    if planned_full and full_tiles != planned_full:
        print(
            f"NOTE: full disk tiles ({len(full_tiles)}) != planned full "
            f"({len(planned_full)})"
        )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="light_bake → full_bake on one world (same generation)",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO / "fixtures" / "world_test_gen.json",
    )
    parser.add_argument(
        "--world-uid",
        default=None,
        help="defaults to fixture world_uid; kept stable across both bakes",
    )
    parser.add_argument(
        "--max-tiles",
        type=int,
        default=None,
        help="debug-only light bake cap; omit/0 = uncapped",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="skip delete/import; bake light→full on existing --world-uid",
    )
    parser.add_argument(
        "--render",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After full bake: dump L0 ASCII (default: on)",
    )
    parser.add_argument(
        "--render-after-light",
        action="store_true",
        help="Also dump render after light (into …/after-light)",
    )
    parser.add_argument(
        "--render-out",
        type=Path,
        default=None,
        help="Render output root (default: .local/map-render/{world_uid}/light-and-full)",
    )
    parser.add_argument(
        "--mark-locations",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()

    fixture = args.fixture.resolve()
    if not fixture.is_file():
        raise SystemExit(f"fixture not found: {fixture}")

    world_uid = args.world_uid or _fixture_world_uid(fixture)
    out_root = args.render_out or (
        REPO / ".local" / "map-render" / world_uid / "light-and-full"
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_latest = out_root / "light-and-full-latest.log"
    log_stamped = out_root / f"light-and-full-{stamp}.log"
    json_latest = out_root / "light-and-full-latest.json"
    json_stamped = out_root / f"light-and-full-{stamp}.json"

    with _tee_stdio(log_latest):
        print(f"report dir: {out_root}")
        print(f"transcript: {log_latest}")

        with api_client() as client:
            client.timeout = _DEFAULT_TIMEOUT_S

            if not args.reuse:
                print(f"reset world for stable uid: {world_uid}")
                api_delete_world(client, world_uid)
                _wipe_local_pack(world_uid)
                imp = _import_fixture(client, str(fixture))
                print(
                    "import:",
                    {
                        k: v for k, v in imp.items()
                        if k not in ("rolled_back", "rollback_reason")
                    },
                )
                r = client.get(f"/worlds/{world_uid}")
                if r.status_code != 200:
                    raise SystemExit(
                        f"after import, world '{world_uid}' missing "
                        f"(HTTP {r.status_code}) — remapped? use --reuse with real uid",
                    )
                api_clear_map(client, world_uid)
                print(f"cleared map patches: {world_uid}")
            else:
                print(f"reuse existing world: {world_uid}")
                r = client.get(f"/worlds/{world_uid}")
                if r.status_code != 200:
                    raise SystemExit(
                        f"world '{world_uid}' not found (HTTP {r.status_code})",
                    )

            light_plan = api_list_bootstrap_tiles(
                client, world_uid, max_tiles=args.max_tiles, scope="light",
            )
            full_plan = api_list_bootstrap_tiles(
                client, world_uid, max_tiles=None, scope="full",
            )
            planned_light = _tiles_from_plan(light_plan)
            planned_full = _tiles_from_plan(full_plan)

            print("\n=== PLAN before bake ===")
            print(
                f"light scope: tile_count={light_plan.get('tile_count')} "
                f"max_tiles={light_plan.get('max_tiles')} capped={light_plan.get('capped')}"
            )
            _print_tile_list("planned light_bake", planned_light)
            print(
                f"full scope:  tile_count={full_plan.get('tile_count')} "
                f"max_tiles={full_plan.get('max_tiles')} capped={full_plan.get('capped')}"
            )
            _print_tile_list("planned full_bake", planned_full)
            _print_tile_list("delta planned (full − light)", planned_full - planned_light)

            print(f"\n--- light_bake → full_bake  world_uid={world_uid} ---")
            _run_bake(client, world_uid, mode="light", max_tiles=args.max_tiles)
            after_light = _snapshot_pack(world_uid)
            _print_stage_inventory("light_bake", after_light)

            if args.render and args.render_after_light:
                print("\n=== map render after light ===")
                summary = dump_map_renders(
                    client,
                    world_uid,
                    out_root=out_root / "after-light",
                    mark_locations=args.mark_locations,
                )
                _print_summary(summary)

            _run_bake(client, world_uid, mode="full", max_tiles=None)
            after_full = _snapshot_pack(world_uid)
            _print_stage_inventory("full_bake", after_full)

            _print_delta_report(
                world_uid=world_uid,
                planned_light=planned_light,
                planned_full=planned_full,
                after_light=after_light,
                after_full=after_full,
            )

            _write_report_json(
                json_latest,
                world_uid=world_uid,
                fixture=str(fixture),
                planned_light=planned_light,
                planned_full=planned_full,
                after_light=after_light,
                after_full=after_full,
            )
            shutil.copyfile(json_latest, json_stamped)
            print(f"\nJSON report: {json_latest}")
            print(f"JSON stamped: {json_stamped}")

            if args.render:
                print("\n=== map render after full ===")
                summary = dump_map_renders(
                    client,
                    world_uid,
                    out_root=out_root / "after-full",
                    mark_locations=args.mark_locations,
                )
                _print_summary(summary)
                print(f"render root: {out_root}")

        # Stamp a copy of the full transcript after tee closes its handle…
        # (copy while still open would race; do after context — see below)

    shutil.copyfile(log_latest, log_stamped)
    print(f"stamped transcript: {log_stamped}")


if __name__ == "__main__":
    main()
