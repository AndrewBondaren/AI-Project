"""One-shot smoke: bootstrap world init + hydrology spot checks."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

BASE = "http://localhost:8000/api"
WORLD = "world-test-all-001"
FIXTURE = REPO / "fixtures" / "world_test_all.json"
CELL_M = 3000


def _ok(r: httpx.Response, ctx: str) -> None:
    if r.status_code >= 400:
        raise SystemExit(f"{ctx}: HTTP {r.status_code}\n{r.text[:3000]}")


def _top_surface(cells: list[dict]) -> list[dict]:
    tops: dict[tuple[int, int], dict] = {}
    for c in cells:
        key = (c["x"], c["y"])
        if key not in tops or c["z"] > tops[key]["z"]:
            tops[key] = c
    return list(tops.values())


def _macro_gx(c: dict) -> int:
    return c["x"] // CELL_M


def _macro_gy(c: dict) -> int:
    return c["y"] // CELL_M


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
            f"/worlds/{WORLD}/map/generate-surface",
            params={"mode": "bootstrap", "max_tiles": 16},
        )
        _ok(r, "generate-surface bootstrap")
        print("surface:", r.json())

        r = c.post(f"/worlds/{WORLD}/map/generate-climate")
        _ok(r, "generate-climate")
        print("climate:", r.json())

        r = c.get(f"/worlds/{WORLD}/map")
        _ok(r, "GET map")
        cells = r.json()

    tops = _top_surface(cells)
    macro_xs = [_macro_gx(c) for c in tops]
    macro_ys = [_macro_gy(c) for c in tops]
    roles: Counter[str] = Counter()
    liquid_body = 0
    liquid_cand = 0
    for c in tops:
        h = c.get("hydrology") or {}
        role = h.get("role")
        if role:
            roles[role] += 1
        if c.get("system_terrain") == "liquid_body":
            liquid_body += 1
        if h.get("liquid_candidate"):
            liquid_cand += 1

    print("--- summary ---")
    print(f"total cells (all z): {len(cells)}")
    print(f"surface-top fine columns: {len(tops)}")
    print(f"macro gx: [{min(macro_xs)}, {max(macro_xs)}]  gy: [{min(macro_ys)}, {max(macro_ys)}]")
    print(f"hydrology roles: {dict(roles)}")
    print(f"liquid_body surface-top: {liquid_body}")
    print(f"liquid_candidate surface-top: {liquid_cand}")

    sea_band = [c for c in tops if 7 <= _macro_gx(c) <= 12 and 0 <= _macro_gy(c) <= 3]
    sea_roles = Counter((c.get("hydrology") or {}).get("role") for c in sea_band)
    sea_liquid = sum(1 for c in sea_band if c.get("system_terrain") == "liquid_body")
    print(f"sea macro gx7-12 gy0-3: roles={dict(sea_roles)} liquid_body={sea_liquid}")

    lake_band = [c for c in tops if 4 <= _macro_gx(c) <= 6 and 1 <= _macro_gy(c) <= 4]
    lake_roles = Counter((c.get("hydrology") or {}).get("role") for c in lake_band)
    lake_liquid = sum(1 for c in lake_band if c.get("system_terrain") == "liquid_body")
    print(f"lake macro gx4-6 gy1-4: roles={dict(lake_roles)} liquid_body={lake_liquid}")

    river_band = [c for c in tops if 2 <= _macro_gx(c) <= 8 and 2 <= _macro_gy(c) <= 6]
    river_roles = Counter((c.get("hydrology") or {}).get("role") for c in river_band)
    river_liquid = sum(1 for c in river_band if c.get("system_terrain") == "liquid_body")
    print(f"river macro gx2-8 gy2-6: roles={dict(river_roles)} liquid_body={river_liquid}")


if __name__ == "__main__":
    main()
