"""Surface materialization helpers — terrain + hydrology + climate (path 2).

These three passes form one logical unit (see ``tz_terrain_generation.md`` § materialization,
``tz_terrain_hydrology.md`` H-7, ``tz_world_generation_dag.md`` § terrain bootstrap):

  1. ``POST …/map/generate-surface``   — heightmap skeleton + column fill
  2. ``POST …/map/generate-hydrology`` — basin / river carve (before climate liquid overlay)
  3. ``POST …/map/generate-climate``   — temperature, rainfall, liquid phase

Ores and caves are **not** part of this stack — optional passes after surface skeleton.

Requires running backend — start it yourself (``npm run backend``).
Shared HTTP client utilities: ``debug_api_helpers.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from debug_api_helpers import BASE_URL, DebugApiError, _require_ok, api_client

SurfaceInitMode = Literal["bootstrap", "full"]
HydrologyScopeQuery = Literal["full", "ocean", "lakes", "rivers", "landforms"]


@dataclass(frozen=True)
class SurfaceStackResult:
    world_uid: str
    surface: dict
    hydrology: dict | None
    climate: dict


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


def api_generate_surface(
    client: httpx.Client,
    world_uid: str,
    *,
    mode: SurfaceInitMode = "bootstrap",
    max_tiles: int = 16,
) -> dict:
    """Run terrain surface batch (coarse plan + fine tiles)."""
    params: dict[str, str | int] = {"mode": mode}
    if max_tiles > 0:
        params["max_tiles"] = max_tiles
    return _post_json(
        client,
        f"/worlds/{world_uid}/map/generate-surface",
        f"POST generate-surface {world_uid} mode={mode}",
        params=params,
    )


def api_list_bootstrap_tiles(
    client: httpx.Client,
    world_uid: str,
    *,
    max_tiles: int = 16,
) -> dict:
    params: dict[str, int] = {}
    if max_tiles > 0:
        params["max_tiles"] = max_tiles
    return _get_json(
        client,
        f"/worlds/{world_uid}/map/bootstrap-tiles",
        f"GET bootstrap-tiles {world_uid}",
        params=params or None,
    )


def api_generate_hydrology(
    client: httpx.Client,
    world_uid: str,
    *,
    scope: HydrologyScopeQuery = "full",
) -> dict:
    """
    Hydrology pass between surface and climate.

    ``scope``: ``full`` | ``ocean`` | ``lakes`` | ``rivers`` | ``landforms``
    """
    return _post_json(
        client,
        f"/worlds/{world_uid}/map/generate-hydrology",
        f"POST generate-hydrology {world_uid} scope={scope}",
        params={"scope": scope},
    )


def api_generate_climate(client: httpx.Client, world_uid: str) -> dict:
    """Climate + liquid overlay on existing map_cells (requires surface first)."""
    return _post_json(
        client,
        f"/worlds/{world_uid}/map/generate-climate",
        f"POST generate-climate {world_uid}",
    )


def api_materialize_surface_stack(
    client: httpx.Client,
    world_uid: str,
    *,
    mode: SurfaceInitMode = "bootstrap",
    max_tiles: int = 16,
    hydrology_scope: HydrologyScopeQuery = "full",
    skip_hydrology: bool = True,
) -> SurfaceStackResult:
    """
    World init stack: surface (bootstrap fine tiles + coarse hydro) → climate.

    Hydrology is merged in ``generate-surface``; set ``skip_hydrology=False`` only to
    re-run the legacy coarse hydrology pass on existing cells.
    """
    surface = api_generate_surface(client, world_uid, mode=mode, max_tiles=max_tiles)

    hydrology: dict | None = None
    if not skip_hydrology:
        hydrology = api_generate_hydrology(client, world_uid, scope=hydrology_scope)

    climate = api_generate_climate(client, world_uid)

    return SurfaceStackResult(
        world_uid=world_uid,
        surface=surface,
        hydrology=hydrology,
        climate=climate,
    )


__all__ = [
    "BASE_URL",
    "DebugApiError",
    "HydrologyScopeQuery",
    "SurfaceInitMode",
    "SurfaceStackResult",
    "api_client",
    "api_generate_climate",
    "api_generate_hydrology",
    "api_generate_surface",
    "api_list_bootstrap_tiles",
    "api_materialize_surface_stack",
]
