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


def api_materialize_stack(
    client: httpx.Client,
    world_uid: str,
    *,
    mode: SurfaceInitMode = "bootstrap",
    max_tiles: int = 16,
    free_cores: int | None = None,
    parallel_workers: int | None = None,
    include_climate: bool = True,
    target: Literal["legacy", "pack"] = "legacy",
) -> dict:
    """S→CL via ``POST materialize-stack`` (shared ``MaterializationContext``)."""
    params: dict[str, str | int | bool] = {
        "mode": mode,
        "include_climate": include_climate,
        "target": target,
    }
    if max_tiles > 0:
        params["max_tiles"] = max_tiles
    if free_cores is not None:
        params["free_cores"] = free_cores
    if parallel_workers is not None:
        params["parallel_workers"] = parallel_workers
    return _post_json(
        client,
        f"/worlds/{world_uid}/map/materialize-stack",
        f"POST materialize-stack {world_uid} mode={mode} target={target}",
        params=params,
    )


def api_pack_bake(
    client: httpx.Client,
    world_uid: str,
    *,
    mode: Literal["light", "tile", "full"] = "light",
    max_tiles: int = 16,
    anchor_x: int | None = None,
    anchor_y: int | None = None,
    heading_dx: int | None = None,
    heading_dy: int | None = None,
) -> dict:
    """World Pack light bake — ``POST …/map/pack/bake`` (target path after WP cutover)."""
    params: dict[str, str | int] = {"mode": mode}
    if max_tiles > 0:
        params["max_tiles"] = max_tiles
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

    Default: ``api_materialize_stack`` (single HTTP, shared parallel context).
    Set ``skip_hydrology=False`` to re-run legacy separate hydrology pass.
    """
    if not skip_hydrology:
        surface = api_generate_surface(client, world_uid, mode=mode, max_tiles=max_tiles)
        hydrology = api_generate_hydrology(client, world_uid, scope=hydrology_scope)
        climate = api_generate_climate(client, world_uid)
        return SurfaceStackResult(
            world_uid=world_uid,
            surface=surface,
            hydrology=hydrology,
            climate=climate,
        )

    stack = api_materialize_stack(
        client, world_uid, mode=mode, max_tiles=max_tiles, include_climate=True,
    )
    return SurfaceStackResult(
        world_uid=world_uid,
        surface=stack.get("terrain", {}),
        hydrology=None,
        climate=stack.get("climate"),
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
    "api_loading_progress",
    "api_materialize_stack",
    "api_materialize_surface_stack",
    "api_pack_bake",
]
