"""The single det-id formula — project_data_storage_tz.md § DET-1.

Three roots, one canonical string ``"{root}|{kind}|{k}={v}"`` hashed by
``uuid5(NAMESPACE_DNS, …)``:

- ``entity_*`` — ``world_uid`` root: identity of generated entities
  (named locations, levels, passages, nodes, cascade rng).
- ``seed_*`` — ``world_seed`` root: bake reproducibility (pack job uid,
  grade catalog uid, relief pick rng).
- ``library_uid`` — no world root: global template libraries; pack-owned
  members use the owner ``pack_uid`` as the canonical root
  (tz_template_library_packs §2).

``world_seed`` today = ``seed_root(world)`` = ``str(world.world_uid)``
(interim until a ``World.seed`` column — tz_terrain_relief §334);
``seed_int`` keeps the legacy md5 derivation used by terrain noise.

``UidKind.REGION`` streams (wilderness plan §5 #4) require a
named ``channel`` key: identical root/kind/keys replay the same stream.
With ``seed = seed_root(world)``, the channel contract is:

- seed grid: ``seeded_u01(seed, REGION, channel=RegionRngChannel.SEED, sx=sx, sy=sy)``
- claim noise: ``seeded_u01(seed, REGION, channel=RegionRngChannel.CLAIM, seed_xy=seed_xy, x=x, y=y)``
- edge noise: ``seed_rng(seed, REGION, channel=RegionRngChannel.EDGE, uid=region_uid, x=x, y=y)``
- density mask: ``seeded_u01(seed, REGION, channel=RegionRngChannel.DENSITY, uid=region_uid, x=x, y=y)``

``RegionRngChannel`` is exported by ``app.ids``; Enum keys normalize to
their string values. ``UidKind.REGION`` also scopes stable region identities;
the source-key adapter is in ``app.ids.regionIdentity``.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from random import Random
from typing import Any
from uuid import NAMESPACE_DNS, uuid4, uuid5

from app.ids.uidKind import LibraryKind, UidKind

UID_PART_SEPARATOR = "|"


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
    return UID_PART_SEPARATOR.join(parts)


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


def seeded_u01(world_seed: str, kind: UidKind, **keys: Any) -> float:
    """Uniform ``[0, 1)`` from the scoped stream."""
    return seed_rng(world_seed, kind, **keys).random()


def seeded_index(world_seed: str, kind: UidKind, n: int, **keys: Any) -> int:
    """Index in ``[0, n)`` from the scoped stream."""
    if n < 1:
        raise ValueError(f"seeded_index n must be >= 1; got {n}")
    return seed_rng(world_seed, kind, **keys).randrange(n)


def library_uid(
    library: LibraryKind, system_name: str, *, pack_uid: str | None = None
) -> str:
    """Uid of a global library template — no world root.

    ``pack_uid=None`` keeps the owner-less canonical
    ``"{library}|{system_name}"`` (bit-compatible, for domains not yet
    migrated to packs). Pack-owned identity puts the owner in the root
    slot of the canonical form: ``"{pack_uid}|{library}|local_uid={system_name}"``.
    ``UID_PART_SEPARATOR`` is rejected in inputs so the serialization cannot
    be ambiguous.
    """
    lib = LibraryKind(library).value
    if UID_PART_SEPARATOR in system_name:
        raise ValueError(
            f"det-id system_name must not contain {UID_PART_SEPARATOR!r}"
        )
    if pack_uid is None:
        return _hash(f"{lib}{UID_PART_SEPARATOR}{system_name}")
    pack = str(pack_uid)
    if not pack or UID_PART_SEPARATOR in pack:
        raise ValueError(
            f"det-id pack_uid must be a non-empty uid without "
            f"{UID_PART_SEPARATOR!r}"
        )
    return _hash(
        f"{pack}{UID_PART_SEPARATOR}{lib}{UID_PART_SEPARATOR}"
        f"local_uid={system_name}"
    )


def runtime_uid() -> str:
    """uuid4 for ``origin='runtime'`` entities — not generation-reproducible."""
    return str(uuid4())


def remapped_library_uid(
    library: LibraryKind, *, target_pack_uid: str, source_template_uid: str
) -> str:
    """Identity of a full-pack copy; readable names never enter the formula."""
    if not target_pack_uid or not source_template_uid:
        raise ValueError("target pack and source member uids are required")
    if any(
        UID_PART_SEPARATOR in value
        for value in (target_pack_uid, source_template_uid)
    ):
        raise ValueError(
            f"remap uids must not contain {UID_PART_SEPARATOR!r}"
        )
    return _hash(
        f"{target_pack_uid}{UID_PART_SEPARATOR}{LibraryKind(library).value}"
        f"{UID_PART_SEPARATOR}source_template_uid={source_template_uid}"
    )


def state_fingerprint(value: Any) -> str:
    """Stable token for structured state; distinct from an entity identity."""
    wire = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)
    return hashlib.sha256(wire.encode("utf-8")).hexdigest()


def seed_root(world: Any) -> str:
    """world_seed wire value — interim ``str(world_uid)`` until World.seed."""
    uid = getattr(world, "world_uid", None)
    if not uid:
        raise ValueError("seed_root requires world.world_uid")
    return str(uid)


def seed_int(world: Any) -> int:
    """Numeric noise seed — legacy md5 derivation (climate/math world_seed)."""
    return int(hashlib.md5(seed_root(world).encode()).hexdigest()[:8], 16)
