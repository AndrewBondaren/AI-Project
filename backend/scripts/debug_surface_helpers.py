"""World Pack debug HTTP helpers — ``POST …/map/pack/bake`` (WP cutover).

Canonical smoke path after L0 light bake + L2 refine (WP-PERF-22).
Legacy ``materialize-stack`` / generate-surface stack is **not** exposed here.

Requires running backend — start it yourself (``npm run backend``).
Shared HTTP client utilities: ``debug_api_helpers.py``.
"""
from __future__ import annotations

from typing import Literal

import httpx

from debug_api_helpers import BASE_URL, DebugApiError, _require_ok, api_client

PackBakeMode = Literal["light", "tile", "full"]


def _get_json(
    client: httpx.Client,
    path: str,
    context: str,
    *,
    params: dict | None = None,
) -> dict:
    r = client.get(path, params=params)
    _require_ok(r, context)
    data = r.json()
    if not isinstance(data, dict):
        raise DebugApiError(f"{context}: expected JSON object, got {type(data)}")
    return data


def _post_json(
    client: httpx.Client,
    path: str,
    context: str,
    *,
    params: dict | None = None,
) -> dict:
    r = client.post(path, params=params)
    _require_ok(r, context)
    data = r.json()
    if not isinstance(data, dict):
        raise DebugApiError(f"{context}: expected JSON object, got {type(data)}")
    return data


def api_list_bootstrap_tiles(
    client: httpx.Client,
    world_uid: str,
    *,
    max_tiles: int = 16,
) -> dict:
    """Preview which macro-tiles light bake will touch."""
    params: dict[str, int] = {}
    if max_tiles > 0:
        params["max_tiles"] = max_tiles
    return _get_json(
        client,
        f"/worlds/{world_uid}/map/bootstrap-tiles",
        f"GET bootstrap-tiles {world_uid}",
        params=params or None,
    )


def api_pack_bake(
    client: httpx.Client,
    world_uid: str,
    *,
    mode: PackBakeMode = "light",
    max_tiles: int | None = None,
    anchor_x: int | None = None,
    anchor_y: int | None = None,
    heading_dx: int | None = None,
    heading_dy: int | None = None,
) -> dict:
    """World Pack bake — L0 world_map + entry refine (``POST …/map/pack/bake``)."""
    from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults

    cap = (
        max_tiles
        if max_tiles is not None
        else PackBakeDefaults.canonical_defaults().max_tiles_light
    )
    params: dict[str, str | int] = {"mode": mode}
    if cap > 0:
        params["max_tiles"] = cap
    if anchor_x is not None:
        params["anchor_x"] = anchor_x
    if anchor_y is not None:
        params["anchor_y"] = anchor_y
    if heading_dx is not None:
        params["heading_dx"] = heading_dx
    if heading_dy is not None:
        params["heading_dy"] = heading_dy
    return _post_json(
        client,
        f"/worlds/{world_uid}/map/pack/bake",
        f"POST pack/bake {world_uid} mode={mode}",
        params=params,
    )


def api_loading_progress(client: httpx.Client, world_uid: str) -> dict:
    return _get_json(
        client,
        f"/worlds/{world_uid}/map/loading-progress",
        f"GET loading-progress {world_uid}",
    )


__all__ = [
    "BASE_URL",
    "DebugApiError",
    "PackBakeMode",
    "api_client",
    "api_list_bootstrap_tiles",
    "api_loading_progress",
    "api_pack_bake",
]
