"""Detailed bake L2 scope — docs/tz_world_pack_storage.md § Bake modes.

Offline ``mode=detailed`` is one product bake with typed scope:
``location`` (territory) or ``wilderness`` (tile L2 topping). Not a third bake mode.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole

DetailedBakeScopeKind = Literal["location", "wilderness"]


class DetailedBakeRequest(BaseModel):
    """Wire/application contract for offline detailed L2 bake."""

    SCHEMA_ID: ClassVar[str] = "SCH-DETAILED-BAKE-REQUEST"

    model_config = ConfigDict(extra="ignore", frozen=True)

    scope: DetailedBakeScopeKind
    location_uid: str | None = None
    # Debug cap for wilderness tiles; 0 = all L0 tiles with world_map_path.
    max_tiles: int = Field(default=0, ge=0)
    # Wilderness single-tile job (recommended debug unit). Both set or both None.
    tile_gx: int | None = None
    tile_gy: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _scope_uid_rules(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        scope = data.get("scope")
        uid = data.get("location_uid")
        gx = data.get("tile_gx")
        gy = data.get("tile_gy")
        if (gx is None) ^ (gy is None):
            raise ValueError("tile_gx and tile_gy must both be set or both omitted")
        if scope == "location":
            uid_s = str(uid).strip() if uid is not None else ""
            if not uid_s:
                raise ValueError("scope=location requires location_uid")
            if gx is not None:
                raise ValueError("tile_gx/tile_gy only apply to scope=wilderness")
            return {**data, "location_uid": uid_s, "tile_gx": None, "tile_gy": None}
        if scope == "wilderness":
            if uid is not None and str(uid).strip():
                raise ValueError("scope=wilderness must not include location_uid")
            return {**data, "location_uid": None}
        return data


def resolve_detailed_bake_request(
    *,
    scope: DetailedBakeScopeKind | None = None,
    location_uid: str | None = None,
    max_tiles: int = 0,
    tile_gx: int | None = None,
    tile_gy: int | None = None,
) -> DetailedBakeRequest:
    """Build validated request. Explicit ``scope`` is SoT.

    Backward-compat: omitted ``scope`` + ``location_uid`` ⇒ ``location``.
    Omitted ``scope`` without uid is an error (do not infer wilderness).
    """
    if scope is None:
        if location_uid and str(location_uid).strip():
            scope = "location"
        else:
            raise ValueError(
                "mode=detailed requires scope=location|wilderness "
                "(or location_uid for scope=location)",
            )
    return DetailedBakeRequest(
        scope=scope,
        location_uid=location_uid,
        max_tiles=max_tiles,
        tile_gx=tile_gx,
        tile_gy=tile_gy,
    )


def refine_role_for_detailed_scope(scope: DetailedBakeScopeKind) -> ChunkRefineRole:
    """Map offline detailed scope → manifest ``ChunkRefineRole``.

    Wilderness uses ``background`` until a dedicated offline role exists.
    """
    if scope == "location":
        return "location"
    return "background"
