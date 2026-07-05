"""One-shot smoke: world_test_all surface stack + hydrology ocean scope."""
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


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=120.0) as c:
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

        r = c.post(f"/worlds/{WORLD}/map/generate-surface")
        _ok(r, "generate-surface")
        print("surface:", r.json())

        r = c.post(f"/worlds/{WORLD}/map/generate-hydrology", params={"scope": "full"})
        _ok(r, "generate-hydrology")
        print("hydrology:", r.json())

        r = c.post(f"/worlds/{WORLD}/map/generate-climate")
        _ok(r, "generate-climate")
        print("climate:", r.json())

        r = c.get(f"/worlds/{WORLD}/map")
        _ok(r, "GET map")
        cells = r.json()

    tops = _top_surface(cells)
    xs = [c["x"] for c in tops]
    ys = [c["y"] for c in tops]
    roles: Counter[str] = Counter()
    liquid_body = 0
    liquid_cand = 0
    meter_orphans = 0
    for c in tops:
        h = c.get("hydrology") or {}
        role = h.get("role")
        if role:
            roles[role] += 1
        if c.get("system_terrain") == "liquid_body":
            liquid_body += 1
        if h.get("liquid_candidate"):
            liquid_cand += 1
        if abs(c["x"]) > 100 or abs(c["y"]) > 100:
            meter_orphans += 1

    print("--- summary ---")
    print(f"total cells (all z): {len(cells)}")
    print(f"surface-top columns: {len(tops)}")
    print(f"grid x: [{min(xs)}, {max(xs)}]  y: [{min(ys)}, {max(ys)}]")
    print(f"hydrology roles: {dict(roles)}")
    print(f"liquid_body surface-top: {liquid_body}")
    print(f"liquid_candidate surface-top: {liquid_cand}")
    print(f"meter-scale orphan coords: {meter_orphans}")

    sea_band = [c for c in tops if 7 <= c["x"] <= 12 and 0 <= c["y"] <= 3]
    sea_roles = Counter((c.get("hydrology") or {}).get("role") for c in sea_band)
    sea_liquid = sum(1 for c in sea_band if c.get("system_terrain") == "liquid_body")
    print(f"sea band gx7-12 gy0-3: roles={dict(sea_roles)} liquid_body={sea_liquid}")

    lake_band = [c for c in tops if 4 <= c["x"] <= 6 and 1 <= c["y"] <= 4]
    lake_roles = Counter((c.get("hydrology") or {}).get("role") for c in lake_band)
    lake_liquid = sum(1 for c in lake_band if c.get("system_terrain") == "liquid_body")
    print(f"lake band gx4-6 gy1-4: roles={dict(lake_roles)} liquid_body={lake_liquid}")


if __name__ == "__main__":
    main()
