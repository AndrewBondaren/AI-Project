"""Pack presence policy — manifest on disk vs ``worlds.terrain_pack_path`` (WP-FIX-DEBT-4)."""

from __future__ import annotations

from pathlib import Path

from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths, resolve_pack_root
from app.db.models.world import World


def pack_root_for_world(
    world: World | None,
    paths: WorldPackPaths,
    *,
    db_path: str,
) -> Path:
    return resolve_pack_root(
        world,
        db_path=db_path,
        world_uid=paths.world_uid,
    )


def pack_manifest_path(
    world: World | None,
    paths: WorldPackPaths,
    *,
    db_path: str,
) -> Path:
    return pack_root_for_world(world, paths, db_path=db_path) / "manifest.json"


def has_pack(
    world: World | None,
    paths: WorldPackPaths,
    *,
    db_path: str,
) -> bool:
    """True when manifest exists at resolved pack root (and optional default fallback)."""
    resolved = pack_root_for_world(world, paths, db_path=db_path)
    if (resolved / "manifest.json").is_file():
        return True
    if world is not None and getattr(world, "terrain_pack_path", None):
        return paths.manifest_path().is_file()
    return False
