"""HTTP helpers for debug scripts — path 2 (see tz_world_generation_dag.md § «Три входа»).

Requires running backend on ``http://localhost:8000`` — **start it yourself** (``npm run backend`` / ``python start.py``).
Agents must **not** start the server; only run these helpers after the user has it up.

Surface materialization stack (terrain + hydrology + climate): ``debug_surface_helpers.py``.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import asdict
from typing import Iterator

import httpx

from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

BASE_URL = os.environ.get("DEBUG_API_URL", "http://localhost:8000/api")
TIMEOUT  = float(os.environ.get("DEBUG_API_TIMEOUT", "120"))


class DebugApiError(RuntimeError):
    pass


def _require_ok(response: httpx.Response, context: str) -> None:
    if response.status_code >= 400:
        raise DebugApiError(
            f"{context}: HTTP {response.status_code}\n{response.text[:2000]}"
        )


def _payload(obj) -> dict:
    return {k: v for k, v in asdict(obj).items() if v is not None}


def location_payload(loc: NamedLocation) -> dict:
    data = _payload(loc)
    data.pop("world_uid", None)
    return data


@contextmanager
def api_client(base_url: str = BASE_URL) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=base_url, timeout=TIMEOUT) as client:
        yield client


def api_delete_world(client: httpx.Client, world_uid: str) -> None:
    api_clear_map(client, world_uid)
    r = client.get(f"/worlds/{world_uid}/locations")
    if r.status_code == 200:
        for loc in r.json():
            client.delete(f"/worlds/{world_uid}/locations/{loc['location_uid']}")
    r = client.delete(f"/worlds/{world_uid}")
    if r.status_code not in (204, 404):
        _require_ok(r, f"DELETE world {world_uid}")


def api_reset_world(
    client: httpx.Client,
    world: World,
    locations: list[NamedLocation],
) -> None:
    api_delete_world(client, world.world_uid)
    r = client.post("/worlds", json=_payload(world))
    _require_ok(r, f"POST /worlds {world.world_uid}")
    for loc in locations:
        r = client.post(
            f"/worlds/{world.world_uid}/locations",
            json=location_payload(loc),
        )
        _require_ok(r, f"POST location {loc.location_uid}")


def api_add_location(client: httpx.Client, loc: NamedLocation) -> None:
    r = client.post(
        f"/worlds/{loc.world_uid}/locations",
        json=location_payload(loc),
    )
    _require_ok(r, f"POST location {loc.location_uid}")


def api_clear_map(client: httpx.Client, world_uid: str) -> None:
    r = client.delete(f"/worlds/{world_uid}/map")
    if r.status_code not in (204, 404):
        _require_ok(r, f"DELETE map {world_uid}")


def api_generate_surface(client: httpx.Client, world_uid: str) -> None:
    r = client.post(f"/worlds/{world_uid}/map/generate-surface")
    _require_ok(r, f"POST generate-surface {world_uid}")


def api_generate_climate(client: httpx.Client, world_uid: str) -> None:
    r = client.post(f"/worlds/{world_uid}/map/generate-climate")
    _require_ok(r, f"POST generate-climate {world_uid}")


def api_get_map(client: httpx.Client, world_uid: str) -> list[dict]:
    r = client.get(f"/worlds/{world_uid}/map")
    _require_ok(r, f"GET map {world_uid}")
    data = r.json()
    if not isinstance(data, list):
        raise DebugApiError(f"GET map {world_uid}: expected list, got {type(data)}")
    return data


def surface_grid_cell(cells: list[dict], gx: int, gy: int) -> dict:
    col = [c for c in cells if c["x"] == gx and c["y"] == gy]
    if not col:
        raise AssertionError(f"no cells at grid ({gx},{gy})")
    return max(col, key=lambda c: c["z"])


def urban_surface_cells(cells: list[dict]) -> set[tuple[int, int]]:
    tops: dict[tuple[int, int], dict] = {}
    for c in cells:
        if c.get("system_terrain") != "urban":
            continue
        key = (c["x"], c["y"])
        if key not in tops or c["z"] > tops[key]["z"]:
            tops[key] = c
    return set(tops.keys())


def top_surface_cells(cells: list[dict]) -> list[dict]:
    by_xy: dict[tuple[int, int], dict] = {}
    for c in cells:
        key = (c["x"], c["y"])
        if key not in by_xy or c["z"] > by_xy[key]["z"]:
            by_xy[key] = c
    return list(by_xy.values())


def api_generate_settlement(
    client: httpx.Client,
    world_uid: str,
    location_uid: str,
    *,
    scope: str = "outdoor",
    skip_if_initialized: bool = True,
) -> dict:
    r = client.post(
        f"/worlds/{world_uid}/locations/{location_uid}/generate-settlement",
        params={"scope": scope, "skip_if_initialized": skip_if_initialized},
    )
    _require_ok(r, f"POST generate-settlement {location_uid}")
    return r.json()


def api_get_location_children(
    client: httpx.Client,
    world_uid: str,
    location_uid: str,
) -> list[dict]:
    r = client.get(f"/worlds/{world_uid}/locations/{location_uid}/children")
    _require_ok(r, f"GET children {location_uid}")
    data = r.json()
    if not isinstance(data, list):
        raise DebugApiError(f"GET children {location_uid}: expected list")
    return data


def api_get_connections(client: httpx.Client, world_uid: str) -> dict:
    r = client.get(f"/worlds/{world_uid}/connections")
    _require_ok(r, f"GET connections {world_uid}")
    data = r.json()
    if not isinstance(data, dict):
        raise DebugApiError(f"GET connections {world_uid}: expected object")
    return data
