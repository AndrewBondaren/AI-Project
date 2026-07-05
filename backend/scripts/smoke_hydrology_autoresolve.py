"""Smoke: world_test.json — hydrology autoresolve without water bundle edges."""
from __future__ import annotations

import sys
from collections import Counter
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


def _top_surface(cells: list[dict]) -> list[dict]:
    tops: dict[tuple[int, int], dict] = {}
    for c in cells:
        key = (c["x"], c["y"])
        if key not in tops or c["z"] > tops[key]["z"]:
            tops[key] = c
    return list(tops.values())


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=120.0) as c:
        r = c.post("/worlds/import", data={"path": str(FIXTURE)})
        _ok(r, "POST /worlds/import")
        print("import:", {k: v.get("succeeded") if isinstance(v, dict) else v for k, v in r.json().items()})

        r = c.delete(f"/worlds/{WORLD}/map")
        if r.status_code not in (204, 404):
            _ok(r, "DELETE map")

        r = c.post(f"/worlds/{WORLD}/map/generate-surface")
        _ok(r, "generate-surface")
        print("surface:", r.json())

        r = c.post(f"/worlds/{WORLD}/map/generate-hydrology", params={"scope": "full"})
        _ok(r, "generate-hydrology")
        body = r.json()
        print("hydrology:", body)

        r = c.get(f"/worlds/{WORLD}/map/cells")
        _ok(r, "GET map/cells")
        tops = _top_surface(r.json())
        roles = Counter()
        liquid = 0
        for cell in tops:
            hyd = cell.get("hydrology") or {}
            role = hyd.get("role")
            if role:
                roles[role] += 1
            if cell.get("system_terrain") == "liquid_body":
                liquid += 1
        print("roles:", dict(roles))
        print("liquid_body cells:", liquid)
        if roles.get("open_ocean", 0) < 10:
            raise SystemExit("expected open_ocean from boundary autoresolve (no bundle water)")
        if roles.get("lake", 0):
            print("autoresolve lakes:", roles["lake"])


if __name__ == "__main__":
    main()
