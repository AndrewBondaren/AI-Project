"""Wilderness refine status policy — WP-12 / docs/tz_world_pack_storage.md."""

from __future__ import annotations

from app.dataModel.worldPack.worldPackManifest import WildernessRefineStatus


def wilderness_refine_status_for_counts(
    baked_chunks: int,
    expected_chunks: int,
) -> WildernessRefineStatus:
    """WP-12 tile wilderness status from chunk coverage."""
    if baked_chunks <= 0:
        return "absent"
    if expected_chunks > 0 and baked_chunks >= expected_chunks:
        return "complete"
    return "partial"


def wilderness_refine_status_without_expected(baked_chunks: int) -> WildernessRefineStatus:
    """Runtime/entry path when full-tile expected count is unknown."""
    return "partial" if baked_chunks > 0 else "absent"
