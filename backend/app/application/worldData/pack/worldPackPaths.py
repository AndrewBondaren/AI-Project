"""Resolve on-disk paths for World Pack artifacts."""

from __future__ import annotations

from pathlib import Path

from app.core.appSettings import app_settings
from app.db.models.world import World


def default_worlds_root(db_path: str | Path) -> Path:
    if app_settings.world_pack_root:
        return Path(app_settings.world_pack_root)
    return Path(db_path).resolve().parent / "worlds"


def resolve_relative_pack_root(rel: str, db_path: str | Path) -> Path:
    path = Path(rel)
    if path.is_absolute():
        return path
    db_parent = Path(db_path).resolve().parent
    if app_settings.world_pack_root:
        pack_parent = Path(app_settings.world_pack_root).resolve().parent
        candidate = (pack_parent / path).resolve()
        if (candidate / "manifest.json").is_file():
            return candidate
    return (db_parent / path).resolve()


def resolve_pack_root(
    world: World | None,
    *,
    db_path: str | Path,
    world_uid: str,
) -> Path:
    """Canonical pack directory for presence checks and I/O (REVIEW-1)."""
    default = WorldPackPaths.from_db_parent(db_path, world_uid).root
    if world is not None and getattr(world, "terrain_pack_path", None):
        return resolve_relative_pack_root(world.terrain_pack_path, db_path)
    return default


class WorldPackPaths:
    """``{pack_root}/`` layout (manifest, tiles/, locations/)."""

    def __init__(self, pack_root: Path, world_uid: str) -> None:
        self.world_uid = world_uid
        self.root = pack_root.resolve()
        self.tiles_dir = self.root / "tiles"
        self.locations_dir = self.root / "locations"

    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def climate_coarse_path(self) -> Path:
        return self.root / "climate_coarse.zst"

    def climate_tile_path(self, gx: int, gy: int) -> Path:
        return self.tiles_dir / f"r.{gx}.{gy}.climate.zst"

    def locations_index_path(self) -> Path:
        return self.root / "locations_index.json"

    def world_map_tile_path(self, gx: int, gy: int) -> Path:
        return self.tiles_dir / f"r.{gx}.{gy}.world_map.zst"

    def wilderness_chunk_path(self, gx: int, gy: int, cx: int, cy: int) -> Path:
        return self.tiles_dir / f"r.{gx}.{gy}.c.{cx}.{cy}.zst"

    def location_terrain_path(self, location_uid: str) -> Path:
        return self.locations_dir / f"l.{location_uid}.terrain.zst"

    def ensure_dirs(self) -> None:
        self.tiles_dir.mkdir(parents=True, exist_ok=True)
        self.locations_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_pack_root(cls, pack_root: Path, world_uid: str) -> WorldPackPaths:
        return cls(pack_root, world_uid)

    @classmethod
    def from_worlds_root(cls, worlds_root: Path, world_uid: str) -> WorldPackPaths:
        return cls(Path(worlds_root) / world_uid / "pack", world_uid)

    @classmethod
    def from_db_parent(cls, db_path: str | Path, world_uid: str) -> WorldPackPaths:
        return cls.from_worlds_root(default_worlds_root(db_path), world_uid)

    @classmethod
    def for_world(cls, world: World, db_path: str | Path) -> WorldPackPaths:
        root = resolve_pack_root(world, db_path=db_path, world_uid=world.world_uid)
        return cls.from_pack_root(root, world.world_uid)
