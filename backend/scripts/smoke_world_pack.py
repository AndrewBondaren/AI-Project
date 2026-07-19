"""WP-A1…A14 World Pack smoke — master/CI (path 2).

Offline gates + unit tests (no backend):
  python scripts/smoke_world_pack.py --offline-only

Full HTTP smoke (backend on localhost:8000 — start it yourself):
  python scripts/smoke_world_pack.py
  python scripts/smoke_world_pack.py --fixture ../fixtures/world_terrain_test.json
  python scripts/smoke_world_pack.py --skip-bake --skip-import

TZ: docs/tz_world_pack_storage.md § WP-A*
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from debug_api_helpers import (
    BASE_URL,
    DebugApiError,
    _require_ok,
    api_clear_map,
    api_client,
    api_pack_bake,
)
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults

DEFAULT_FIXTURE = REPO / "fixtures" / "world_terrain_test.json"
DEFAULT_WORLD = "world-terrain-test-001"

LIMITS = {
    "A1_bake_s": 120,
    "A2_cold_load_s": 300,
    "A9_scene_volume_s": 30,
    "A10_scene_volume_s": 10,
}

MANUAL = {
    "WP-A4": "fine-terrain refine golden hash — run twice, compare chunk content_hash in manifest",
    "WP-A8": "kill mid-chunk — verify saved chunks + stable hash on redo",
    "WP-A14": "stale world map regen from location boundary — manual regen pass",
}

# WP-PERF-10: light bake must not enqueue whole macro-tile (~8k jobs).
A5_MAX_REFINE_QUEUE = PackBakeDefaults.canonical_defaults().smoke_max_refine_queue_depth


class SmokeResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.skipped: list[str] = []

    def ok(self, case_id: str, detail: str = "") -> None:
        msg = f"{case_id} PASS" + (f" — {detail}" if detail else "")
        print(msg)
        self.passed.append(case_id)

    def fail(self, case_id: str, detail: str) -> None:
        msg = f"{case_id} FAIL — {detail}"
        print(msg, file=sys.stderr)
        self.failed.append(case_id)

    def skip(self, case_id: str, reason: str) -> None:
        print(f"{case_id} SKIP — {reason}")
        self.skipped.append(case_id)

    def exit_code(self) -> int:
        return 1 if self.failed else 0


def _run_cmd(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def run_offline(result: SmokeResult) -> None:
    gate = _run_cmd([sys.executable, "scripts/check_no_wilderness_insert.py"], cwd=BACKEND)
    if gate.returncode == 0:
        result.ok("WP-A7", "no wilderness INSERT INTO map_cells")
    else:
        result.fail("WP-A7", (gate.stderr or gate.stdout or "gate failed").strip()[:500])

    tests = [
        "tests.test_merge_fieldwise",
        "tests.test_merge_map_cells",
        "tests.test_merge9_debug_read",
        "tests.test_pack_fine_terrain_decode_cache",
        "tests.test_wp_acceptance",
        "tests.test_location_territory_volumes",
        "tests.test_pack_root_resolution",
        "tests.test_pack_climate_apply",
        "tests.test_pojo_policies",
    ]
    proc = _run_cmd(
        [sys.executable, "-m", "unittest", "-q", *tests],
        cwd=BACKEND,
    )
    if proc.returncode == 0:
        result.ok("WP-unit", f"{len(tests)} unittest modules")
    else:
        tail = (proc.stderr or proc.stdout or "")[-2000:]
        result.fail("WP-unit", tail)


def _fixture_world_uid(fixture: Path) -> str:
    data = json.loads(fixture.read_text(encoding="utf-8"))
    return data.get("world", data).get("world_uid") or DEFAULT_WORLD


def _spawn_anchor(fixture: Path) -> tuple[int, int, int]:
    data = json.loads(fixture.read_text(encoding="utf-8"))
    for loc in data.get("locations") or []:
        if loc.get("map_x") is not None and loc.get("map_y") is not None:
            z = int(loc.get("map_z") or 0)
            return int(loc["map_x"]), int(loc["map_y"]), z
    return 0, 0, 0


def _import_fixture(client: httpx.Client, fixture: Path) -> dict:
    r = client.post("/worlds/import", data={"path": str(fixture.resolve())})
    _require_ok(r, f"POST /worlds/import {fixture.name}")
    return r.json()


def run_http(
    result: SmokeResult,
    *,
    fixture: Path,
    world_uid: str,
    max_tiles: int,
    skip_import: bool,
    skip_bake: bool,
    base_url: str,
) -> None:
    try:
        with api_client(base_url=base_url) as client:
            r = client.get("/worlds")
            _require_ok(r, "GET /worlds")
    except (httpx.ConnectError, DebugApiError) as exc:
        result.fail("HTTP", f"backend not reachable at {base_url}: {exc}")
        return

    with api_client(base_url=base_url) as client:
        if not skip_import:
            imp = _import_fixture(client, fixture)
            brief = {
                k: v.get("succeeded") if isinstance(v, dict) else v
                for k, v in imp.items()
                if k not in ("rolled_back", "rollback_reason")
            }
            print("import:", brief)

        api_clear_map(client, world_uid)

        if not skip_bake:
            t0 = time.perf_counter()
            bake = api_pack_bake(client, world_uid, max_tiles=max_tiles)
            elapsed = time.perf_counter() - t0
            terrain = bake.get("terrain") or {}
            failed = int(terrain.get("failed") or 0)
            if failed > 0:
                result.fail("WP-A1", f"pack bake terrain.failed={failed}")
            elif elapsed > LIMITS["A1_bake_s"]:
                result.fail("WP-A1", f"bake {elapsed:.1f}s > {LIMITS['A1_bake_s']}s")
            else:
                wm = (bake.get("loading_progress") or {}).get("worldMapLoading") or {}
                tiles_ready = int(wm.get("tiles_ready") or 0)
                tiles_pct = wm.get("tiles_pct")
                result.ok(
                    "WP-A1",
                    f"light bake {elapsed:.1f}s, tiles_ready={tiles_ready}, tiles_pct={tiles_pct}",
                )
            queue_depth = bake.get("refine_queue_depth")
            if isinstance(queue_depth, int) and queue_depth <= A5_MAX_REFINE_QUEUE:
                result.ok(
                    "WP-A5",
                    f"refine_queue_depth={queue_depth} <= {A5_MAX_REFINE_QUEUE} (rings, not whole tile)",
                )
            elif isinstance(queue_depth, int):
                result.fail(
                    "WP-A5",
                    f"refine_queue_depth={queue_depth} > {A5_MAX_REFINE_QUEUE} — WP-PERF-10 full-tile enqueue?",
                )
            else:
                result.fail("WP-A5", "bake response missing refine_queue_depth")
        else:
            result.skip("WP-A1", "--skip-bake")
            result.skip("WP-A5", "--skip-bake")

        t0 = time.perf_counter()
        r = client.get(f"/worlds/{world_uid}/map")
        _require_ok(r, f"GET map {world_uid}")
        cells = r.json()
        cold_s = time.perf_counter() - t0
        if not isinstance(cells, list) or not cells:
            result.fail("WP-A2", "GET /map returned empty — pack missing?")
        elif cold_s > LIMITS["A2_cold_load_s"]:
            result.fail("WP-A2", f"cold map read {cold_s:.1f}s > {LIMITS['A2_cold_load_s']}s")
        else:
            result.ok("WP-A2", f"GET /map {len(cells)} cells in {cold_s:.2f}s")

        terrains = {c.get("system_terrain") for c in cells if c.get("system_terrain")}
        hydro = sum(1 for c in cells if c.get("hydrology_role"))
        r = client.get(f"/worlds/{world_uid}/locations")
        _require_ok(r, f"GET locations {world_uid}")
        locs = r.json()
        if isinstance(locs, list) and locs and terrains:
            result.ok("WP-A3", f"{len(locs)} locations, world_map terrains={sorted(terrains)[:5]}, hydro_cells={hydro}")
        else:
            result.fail("WP-A3", f"locations={len(locs) if isinstance(locs, list) else '?'}, terrains={terrains}")

        r = client.get(f"/worlds/{world_uid}/map/loading-progress")
        _require_ok(r, "GET loading-progress")
        progress = r.json()
        wm = progress.get("worldMapLoading") or progress.get("world_map") or {}
        tiles_pct = wm.get("tiles_pct")
        locations_pct = wm.get("locations_pct")
        wilderness_pct = wm.get("wilderness_pct")
        if all(isinstance(v, (int, float)) for v in (tiles_pct, locations_pct, wilderness_pct)):
            result.ok(
                "WP-A11",
                f"tiles={tiles_pct}% locations={locations_pct}% "
                f"wilderness={wilderness_pct}% phase={wm.get('phase')}",
            )
        else:
            result.fail("WP-A11", "loading-progress missing tiles/locations/wilderness_pct")

        ax, ay, az = _spawn_anchor(fixture)
        t0 = time.perf_counter()
        r = client.get(
            f"/worlds/{world_uid}/map/scene-volume",
            params={"x": ax, "y": ay, "z": az},
        )
        _require_ok(r, f"GET scene-volume ({ax},{ay},{az})")
        scene = r.json()
        scene_s = time.perf_counter() - t0
        count = int(scene.get("cell_count") or 0)
        if count <= 0:
            result.fail("WP-A9", "scene-volume empty")
        elif scene_s > LIMITS["A9_scene_volume_s"]:
            result.fail("WP-A9", f"{scene_s:.1f}s > {LIMITS['A9_scene_volume_s']}s, cells={count}")
        else:
            result.ok("WP-A9", f"scene-volume {count} cells in {scene_s:.2f}s at ({ax},{ay},{az})")

        t0 = time.perf_counter()
        r = client.post(
            f"/worlds/{world_uid}/map/refine-from-entry",
            params={"x": ax, "y": ay, "kind": "session_start", "schedule_bg": "true"},
        )
        _require_ok(r, f"POST refine-from-entry ({ax},{ay})")
        entry = r.json()
        entry_s = time.perf_counter() - t0
        entry_q = entry.get("refine_queue_depth")
        if entry_s > LIMITS["A9_scene_volume_s"]:
            result.fail("WP-A9b", f"refine-from-entry {entry_s:.1f}s > {LIMITS['A9_scene_volume_s']}s")
        elif isinstance(entry_q, int) and entry_q <= A5_MAX_REFINE_QUEUE:
            result.ok(
                "WP-A9b",
                f"refine-from-entry {entry_s:.2f}s queue={entry_q} chunks_done={entry.get('chunks_done')}",
            )
        else:
            result.fail("WP-A9b", f"refine-from-entry queue={entry_q} (expected int <= {A5_MAX_REFINE_QUEUE})")

        alt_x, alt_y = ax + 3000, ay + 3000
        t0 = time.perf_counter()
        r = client.get(
            f"/worlds/{world_uid}/map/scene-volume",
            params={"x": alt_x, "y": alt_y, "z": az},
        )
        _require_ok(r, f"GET scene-volume alt ({alt_x},{alt_y})")
        alt = r.json()
        alt_s = time.perf_counter() - t0
        alt_count = int(alt.get("cell_count") or 0)
        if alt_count <= 0:
            result.fail("WP-A10", "alt macro-tile scene-volume empty")
        elif alt_s > LIMITS["A10_scene_volume_s"]:
            result.fail("WP-A10", f"{alt_s:.1f}s > {LIMITS['A10_scene_volume_s']}s")
        else:
            result.ok("WP-A10", f"alt tile {alt_count} cells in {alt_s:.2f}s")

        has_climate = any(
            c.get("temperature_base") is not None or c.get("rainfall") is not None
            for c in scene.get("cells") or []
        )
        if has_climate:
            result.ok("WP-A12", "scene cells include climate fields")
        else:
            result.fail("WP-A12", "scene cells missing temperature_base/rainfall — climate_coarse bake required")

        building = [c for c in scene.get("cells") or [] if c.get("system_building_element")]
        if building:
            result.ok("WP-A6", f"{len(building)} building cells in scene-volume")
        else:
            result.skip("WP-A6", "no settlement patch in fixture — covered by unit test_wp_acceptance")

    for case_id, note in MANUAL.items():
        result.skip(case_id, note)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="World Pack WP-A smoke")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--world-uid", default=None)
    parser.add_argument(
        "--max-tiles",
        type=int,
        default=0,
        help="debug-only light bake cap; 0=uncapped (all location tiles)",
    )
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--offline-only", action="store_true")
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--skip-bake", action="store_true")
    args = parser.parse_args()

    fixture = args.fixture.resolve()
    if not fixture.is_file():
        raise SystemExit(f"fixture not found: {fixture}")

    world_uid = args.world_uid or _fixture_world_uid(fixture)
    result = SmokeResult()

    run_offline(result)
    if not args.offline_only:
        run_http(
            result,
            fixture=fixture,
            world_uid=world_uid,
            max_tiles=args.max_tiles,
            skip_import=args.skip_import,
            skip_bake=args.skip_bake,
            base_url=args.base_url,
        )
    else:
        for case_id, note in MANUAL.items():
            result.skip(case_id, f"HTTP only — {note}")

    print(
        f"\nSummary: {len(result.passed)} passed, "
        f"{len(result.failed)} failed, {len(result.skipped)} skipped"
    )
    raise SystemExit(result.exit_code())


if __name__ == "__main__":
    main()
