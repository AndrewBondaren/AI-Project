"""One-shot smoke: world_test_all via World Pack light bake + L0 tile grids."""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

BASE = "http://localhost:8000/api"
WORLD = "world-test-all-001"
FIXTURE = REPO / "fixtures" / "world_test_all.json"


def _ok(r: httpx.Response, ctx: str) -> None:
    if r.status_code >= 400:
        raise SystemExit(f"{ctx}: HTTP {r.status_code}\n{r.text[:3000]}")


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=600.0) as c:
        r = c.get("/worlds")
        _ok(r, "GET /worlds")
        print(f"worlds in DB: {len(r.json())}")

        r = c.post("/worlds/import", data={"path": str(FIXTURE)})
        _ok(r, "POST /worlds/import")
        imp = r.json()
        brief = {
            k: v.get("succeeded") if isinstance(v, dict) else v
            for k, v in imp.items()
            if k not in ("rolled_back", "rollback_reason")
        }
        print("import:", brief)

        r = c.delete(f"/worlds/{WORLD}/map")
        if r.status_code not in (204, 404):
            _ok(r, "DELETE map")

        r = c.get(f"/worlds/{WORLD}/map/bootstrap-tiles", params={"max_tiles": 16})
        _ok(r, "bootstrap-tiles")
        preview = r.json()
        print(f"bootstrap preview: {preview.get('tile_count')} tiles")

        r = c.post(
            f"/worlds/{WORLD}/map/pack/bake",
            params={"mode": "light", "max_tiles": 16},
        )
        _ok(r, "pack/bake")
        bake = r.json()
        print("pack bake:", {
            "world_map_cells": bake.get("world_map_cells"),
            "terrain": bake.get("terrain"),
            "climate_coarse_samples": bake.get("climate_coarse_samples"),
            "chunks_done": bake.get("chunks_done"),
        })

        r = c.get(f"/worlds/{WORLD}/map/render-world-tile-grids")
        _ok(r, "render-world-tile-grids")
        tiles = (r.json() or {}).get("tiles") or {}
        if not tiles:
            raise SystemExit("expected L0 tile grids after pack/bake")
        print(f"L0 tile grids: {len(tiles)}")


if __name__ == "__main__":
    main()
