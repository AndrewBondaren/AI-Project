"""Smoke: world + location ASCII grid debug endpoints (path 2).

Artifacts: ``.local/grid-render/{world_uid}/`` (gitignored).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

BASE = "http://localhost:8000/api"
WORLD = "world-test-all-001"
FIXTURE = REPO / "fixtures" / "world_test_all.json"
HAMLET = "loc-template-settlement-hamlet"
OUT_DIR = REPO / ".local" / "grid-render" / WORLD


def _ok(r: httpx.Response, ctx: str) -> None:
    if r.status_code >= 400:
        raise SystemExit(f"{ctx}: HTTP {r.status_code}\n{r.text[:3000]}")


def _preview(text: str, *, lines: int = 12) -> str:
    rows = text.strip().splitlines()
    head = "\n".join(rows[:lines])
    if len(rows) > lines:
        head += f"\n... ({len(rows) - lines} more lines)"
    return head


def _write_artifact(name: str, content: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    written: list[Path] = []

    with httpx.Client(base_url=BASE, timeout=120.0) as c:
        r = c.get("/worlds")
        _ok(r, "GET /worlds")
        print(f"worlds in DB before import: {len(r.json())}")

        r = c.post("/worlds/import", data={"path": str(FIXTURE)})
        _ok(r, "POST /worlds/import")
        imp = r.json()
        print("import:", {k: v.get("succeeded") if isinstance(v, dict) else v for k, v in imp.items()})

        r = c.delete(f"/worlds/{WORLD}/map")
        if r.status_code not in (204, 404):
            _ok(r, "DELETE map")

        r = c.post(f"/worlds/{WORLD}/map/generate-surface")
        _ok(r, "generate-surface")
        print("surface:", r.json())

        r = c.post(f"/worlds/{WORLD}/map/generate-hydrology", params={"scope": "full"})
        _ok(r, "generate-hydrology")
        print("hydrology:", r.json())

        r = c.get(f"/worlds/{WORLD}/map/render-world-grid")
        _ok(r, "GET render-world-grid")
        world_grid = r.json()
        ascii_grid = world_grid.get("ascii", "")
        legend = world_grid.get("legend", "")
        if not ascii_grid.strip():
            raise SystemExit("render-world-grid: empty ascii")
        if not legend.strip():
            raise SystemExit("render-world-grid: missing legend")
        written.append(_write_artifact(f"world-grid-{stamp}.txt", f"{ascii_grid}\n\n--- legend ---\n{legend}"))
        print("--- render-world-grid (auto bbox) ---")
        print(_preview(ascii_grid))
        print("legend:", legend.replace("\n", " | "))

        r = c.get(
            f"/worlds/{WORLD}/map/render-world-grid",
            params={"gx0": 0, "gy0": 0, "gx1": 15, "gy1": 10},
        )
        _ok(r, "GET render-world-grid bbox")
        bbox_grid = r.json().get("ascii", "")
        written.append(_write_artifact(f"world-grid-bbox-{stamp}.txt", bbox_grid))
        print("--- render-world-grid bbox 0,0..15,10 ---")
        print(_preview(bbox_grid, lines=8))

        r = c.post(
            f"/worlds/{WORLD}/locations/{HAMLET}/generate-settlement",
            params={"skip_if_initialized": "false"},
        )
        _ok(r, f"generate-settlement {HAMLET}")
        settlement_body = r.json()
        print("settlement map_cells:", settlement_body.get("map_cells"))
        written.append(_write_artifact(
            f"settlement-{HAMLET}-{stamp}.json",
            json.dumps(settlement_body, ensure_ascii=False, indent=2),
        ))

        r = c.get(f"/worlds/{WORLD}/locations/{HAMLET}/render-grid")
        _ok(r, "GET render-grid (all levels)")
        loc_grid = r.json()
        levels = loc_grid.get("levels") or {}
        if not levels:
            raise SystemExit("render-grid: no levels after settlement generate")
        z0 = levels.get(0) or levels.get(min(levels))
        if not z0 or not str(z0).strip():
            raise SystemExit("render-grid: empty level 0 ascii")
        loc_text = "\n\n".join(f"=== z={z} ===\n{grid}" for z, grid in sorted(levels.items()))
        written.append(_write_artifact(
            f"location-grid-{HAMLET}-{stamp}.txt",
            f"{loc_text}\n\n--- legend ---\n{loc_grid.get('legend', '')}",
        ))
        print(f"--- render-grid {HAMLET} levels={sorted(levels)} ---")
        print(_preview(str(z0), lines=10))

        r = c.get(f"/worlds/{WORLD}/locations/{HAMLET}/render-grid", params={"z": 0})
        _ok(r, "GET render-grid z=0")
        z_payload = r.json()
        if z_payload.get("z") != 0:
            raise SystemExit("render-grid z=0: missing z field")
        if not str(z_payload.get("ascii", "")).strip():
            raise SystemExit("render-grid z=0: empty ascii")

    print("\n[OK] grid render smoke passed")
    print(f"artifacts: {OUT_DIR}")
    for path in written:
        print(f"  - {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
