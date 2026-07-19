"""World Pack debug HTTP helpers — ``POST …/map/pack/bake`` (WP cutover).

Canonical smoke path after L0 light bake + L2 refine (WP-PERF-22).
Legacy ``materialize-stack`` / generate-surface stack is **not** exposed here.

Requires running backend — start it yourself (``npm run backend``).
Shared HTTP client utilities: ``debug_api_helpers.py``.
Canonical ``api_pack_bake`` lives in ``debug_api_helpers`` (re-exported here).
"""
from __future__ import annotations

import httpx

from debug_api_helpers import (
    BASE_URL,
    DebugApiError,
    _require_ok,
    api_client,
    api_pack_bake,
)

# Re-export mode typing from helpers module contract
PackBakeMode = str  # "light" | "tile" | "full" — validated by HTTP API


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


def api_list_bootstrap_tiles(
    client: httpx.Client,
    world_uid: str,
    *,
    max_tiles: int | None = None,
) -> dict:
    """Preview which macro-tiles light bake will touch (0 = uncapped)."""
    params: dict[str, int] = {
        "max_tiles": 0 if max_tiles is None else int(max_tiles),
    }
    return _get_json(
        client,
        f"/worlds/{world_uid}/map/bootstrap-tiles",
        f"GET bootstrap-tiles {world_uid}",
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
