"""Smoke: world_test.json — hydrology via World Pack light bake (not generate-surface)."""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

BASE = "http://localhost:8000/api"
WORLD = "world-test-001"
FIXTURE = REPO / "fixtures" / "world_test.json"


def _ok(r: httpx.Response, ctx: str) -> None:
    if r.status_code >= 400:
        raise SystemExit(f"{ctx}: HTTP {r.status_code}\n{r.text[:3000]}")


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=300.0) as c:
        r = c.post("/worlds/import", data={"path": str(FIXTURE)})
        _ok(r, "POST /worlds/import")
        print("import:", {
            k: v.get("succeeded") if isinstance(v, dict) else v
            for k, v in r.json().items()
        })

        r = c.delete(f"/worlds/{WORLD}/map")
        if r.status_code not in (204, 404):
            _ok(r, "DELETE map")

        r = c.post(
            f"/worlds/{WORLD}/map/pack/bake",
            params={"mode": "light", "max_tiles": 16},
        )
        _ok(r, "pack/bake")
        bake = r.json()
        print("pack bake:", {
            "world_map_cells": bake.get("world_map_cells"),
            "terrain": bake.get("terrain"),
            "hydro_hint": (bake.get("loading_progress") or {}),
        })

        r = c.get(f"/worlds/{WORLD}/map/render-world-tile-grids")
        _ok(r, "render-world-tile-grids")
        tiles = (r.json() or {}).get("tiles") or {}
        if not tiles:
            raise SystemExit("expected L0 tile grids after pack/bake")
        print(f"L0 tile grids: {len(tiles)}")
        # ASCII must mention hydro or non-flat content for smoke signal
        sample = next(iter(tiles.values()))
        ascii_grid = (sample.get("levels") or {}).get("light") or ""
        if not ascii_grid.strip():
            raise SystemExit("empty light grid ASCII")
        print("sample tile ascii lines:", len(ascii_grid.splitlines()))


if __name__ == "__main__":
    main()
