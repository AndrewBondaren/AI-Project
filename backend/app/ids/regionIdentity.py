"""Region identity keys over DET-1; no world reads or diagnostic dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unicodedata import normalize

from app.ids.deterministicIds import UID_PART_SEPARATOR, entity_uid
from app.ids.uidKind import UidKind


if TYPE_CHECKING:
    from app.dataModel.spatial.regionShape import RegionShapeKind


def normalize_region_name(name: str | None) -> str | None:
    """Shared by the Spec validator and direct identity calls; case is preserved."""
    value = normalize("NFC", name.strip()) if name is not None else None
    if value is not None and UID_PART_SEPARATOR in value:
        raise ValueError(f"region name must not contain {UID_PART_SEPARATOR!r}")
    return value or None


def region_uid(
    world_uid: str,
    *,
    name: str | None = None,
    anchor_uid: str | None = None,
    seed_xy: tuple[int, int] | None = None,
    region_seed_xy: tuple[int, int] | None = None,
    bbox_min: tuple[int, int] | None = None,
    shape_kind: RegionShapeKind | None = None,
) -> str:
    """Use exactly one identity source; geometry/type/density are never keys.

    Anonymous declarations pass anchor_uid or bbox_min+shape_kind after the caller
    reports degraded identity. Anchor and autoresolve callers use their own
    stable identity directly, with no declaration fallback semantics.
    Aggregated autoresolve regions use region_seed_xy; individual seed parts use
    seed_xy. Distinct DET-1 keys prevent parent/child identity aliasing.
    """
    name = normalize_region_name(name)
    if sum(value is not None for value in (name, anchor_uid, seed_xy, region_seed_xy, bbox_min)) != 1:
        raise ValueError("region_uid requires exactly one identity source")
    if (bbox_min is not None) != (shape_kind is not None):
        raise ValueError("bbox_min and shape_kind must be supplied together")
    if shape_kind is not None:
        # dataModel imports app.ids during package initialization.
        from app.dataModel.spatial.regionShape import RegionShapeKind

        if not isinstance(shape_kind, RegionShapeKind):
            raise TypeError("shape_kind must be a RegionShapeKind")
        if shape_kind is RegionShapeKind.ANCHOR_RADIUS:
            raise ValueError("anchor_radius identity requires anchor_uid, not bbox_min")
    if name is not None:
        return entity_uid(world_uid, UidKind.REGION, name=name)
    if anchor_uid is not None:
        if not anchor_uid or UID_PART_SEPARATOR in anchor_uid:
            raise ValueError("anchor_uid must be nonempty and contain no UID separator")
        return entity_uid(world_uid, UidKind.REGION, anchor_uid=anchor_uid)
    if region_seed_xy is not None:
        return entity_uid(world_uid, UidKind.REGION, region_seed_xy=region_seed_xy)
    if seed_xy is not None:
        return entity_uid(world_uid, UidKind.REGION, seed_xy=seed_xy)
    return entity_uid(world_uid, UidKind.REGION, bbox_min=bbox_min, shape_kind=shape_kind)
