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

HydrologyScopeQuery = Literal["full", "ocean", "lakes", "rivers", "landforms"]


@dataclass(frozen=True)
class SurfaceStackResult:
    world_uid: str
    surface: dict
    hydrology: dict | None
    climate: dict


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


def api_generate_surface(client: httpx.Client, world_uid: str) -> dict:
    """Run terrain skeleton batch (pole → surface → gap → column fill)."""
    return _post_json(
        client,
        f"/worlds/{world_uid}/map/generate-surface",
        f"POST generate-surface {world_uid}",
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
    hydrology_scope: HydrologyScopeQuery = "full",
    skip_hydrology: bool = False,
) -> SurfaceStackResult:
    """
    Full surface materialization: surface → hydrology → climate.

    Use after world + locations exist in DB. Does not clear map — call
    ``debug_api_helpers.api_clear_map`` first for regen.
    """
    surface = api_generate_surface(client, world_uid)

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
    "SurfaceStackResult",
    "api_client",
    "api_generate_climate",
    "api_generate_hydrology",
    "api_generate_surface",
    "api_materialize_surface_stack",
]
