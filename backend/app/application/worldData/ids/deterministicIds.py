"""The single det-id formula — project_data_storage_tz.md § DET-1.

Three roots, one canonical string ``"{root}|{kind}|{k}={v}"`` hashed by
``uuid5(NAMESPACE_DNS, …)``:

- ``entity_*`` — ``world_uid`` root: identity of generated entities
  (named locations, levels, passages, nodes, cascade rng).
- ``seed_*`` — ``world_seed`` root: bake reproducibility (pack job uid,
  grade catalog uid, relief pick rng).
- ``library_uid`` — no world root: global template libraries.

``world_seed`` today = ``seed_root(world)`` = ``str(world.world_uid)``
(interim until a ``World.seed`` column — tz_terrain_relief §334);
``seed_int`` keeps the legacy md5 derivation used by terrain noise.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from random import Random
from typing import Any
from uuid import NAMESPACE_DNS, uuid4, uuid5

from app.application.worldData.ids.uidKind import LibraryKind, UidKind

_SEP = "|"


def _normalize(value: Any) -> str:
    if value is None:
        raise ValueError("det-id key value must not be None")
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, (tuple, list)):
        return ",".join(_normalize(v) for v in value)
    raise ValueError(
        f"det-id key value of type {type(value).__name__} is not supported"
    )


def _canonical(root: str, kind: UidKind, keys: dict[str, Any]) -> str:
    parts = [str(root), UidKind(kind).value]
    for name in sorted(keys):
        parts.append(f"{name}={_normalize(keys[name])}")
    return _SEP.join(parts)


def _hash(canonical: str) -> str:
    return str(uuid5(NAMESPACE_DNS, canonical))


def entity_uid(world_uid: str, kind: UidKind, **keys: Any) -> str:
    """Deterministic uid of a generated entity (world_uid root)."""
    return _hash(_canonical(world_uid, kind, keys))


def entity_rng(world_uid: str, kind: UidKind, **keys: Any) -> Random:
    """Independent rng stream of a generated entity (world_uid root)."""
    return Random(entity_uid(world_uid, kind, **keys))


def seed_uid(world_seed: str, kind: UidKind, **keys: Any) -> str:
    """Deterministic uid under the bake root (world_seed)."""
    return _hash(_canonical(world_seed, kind, keys))


def seed_rng(world_seed: str, kind: UidKind, **keys: Any) -> Random:
    """Independent rng stream under the bake root (world_seed)."""
    return Random(seed_uid(world_seed, kind, **keys))


def library_uid(library: LibraryKind, system_name: str) -> str:
    """Uid of a global library template — no world root."""
    return _hash(f"{LibraryKind(library).value}{_SEP}{system_name}")


def runtime_uid() -> str:
    """uuid4 for ``origin='runtime'`` entities — not generation-reproducible."""
    return str(uuid4())


def seed_root(world: Any) -> str:
    """world_seed wire value — interim ``str(world_uid)`` until World.seed."""
    uid = getattr(world, "world_uid", None)
    if not uid:
        raise ValueError("seed_root requires world.world_uid")
    return str(uid)


def seed_int(world: Any) -> int:
    """Numeric noise seed — legacy md5 derivation (climate/math world_seed)."""
    return int(hashlib.md5(seed_root(world).encode()).hexdigest()[:8], 16)
