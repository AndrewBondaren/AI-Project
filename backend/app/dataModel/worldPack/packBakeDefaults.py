"""Pack bake defaults — single source for debug orchestration caps."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.worldPack.lightFineTilePolicy import LightFineTilePolicy


class PackBakeDefaults(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-PACK-BAKE-DEFAULTS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    # Debug-only light bake slice. 0 = uncapped (product default: all location∪hydro tiles).
    max_tiles_light: int = Field(default=0, ge=0)
    zstd_level: int = 3
    codec_version: int = 1
    background_drain_per_request: int = 0
    # WP-11 single-writer: at most one active background chunk job.
    refine_queue_max_workers: int = Field(default=1, ge=1)
    # WP-PERF-10 / WP-A5: light/entry refine queue depth must stay well below whole-tile enqueue.
    smoke_max_refine_queue_depth: int = Field(default=200, ge=0)
    detailed_include_climate_fine: bool = True
    # When to write r.{gx}.{gy}.climate.zst on light/full L0 bake.
    light_fine_tile_policy: LightFineTilePolicy = "spawn_player"
    # full_bake default: defer denser climate to detailed / runtime.
    full_fine_tile_policy: LightFineTilePolicy = "none"

    @classmethod
    def canonical_defaults(cls) -> PackBakeDefaults:
        return cls()


def resolve_light_tile_cap(
    max_tiles: int | None,
    *,
    defaults: PackBakeDefaults | None = None,
) -> int | None:
    """Normalize light-bake debug tile cap.

    ``None`` → ``defaults.max_tiles_light`` (``<=0`` means uncapped);
    ``<= 0`` → ``None`` (no cap);
    ``> 0`` → that cap.

    Product default is uncapped (``max_tiles_light=0``). Positive values are
    debug/smoke overrides only — not product light scope.
    """
    defs = defaults or PackBakeDefaults.canonical_defaults()
    if max_tiles is None:
        raw = int(defs.max_tiles_light)
        return None if raw <= 0 else raw
    if int(max_tiles) <= 0:
        return None
    return int(max_tiles)
