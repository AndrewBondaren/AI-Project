"""C14 settlement packing status — docs/tz_settlement_outdoor.md / pack C24."""

from __future__ import annotations

from collections.abc import Sequence

from app.dataModel.worldPack.worldPackManifest import SettlementStructureStatus


def settlement_structure_status_for(
    packed_uids: Sequence[str],
    census_uids: Sequence[str],
    *,
    has_file: bool,
) -> SettlementStructureStatus:
    """complete iff packed = C23 census and the C15 file is on disk."""
    packed = list(packed_uids)
    census = list(census_uids)
    if not packed:
        return "absent"
    if has_file and census and set(packed) == set(census):
        return "complete"
    return "partial"
