"""LOC-T-3 settlement volume occupancy ERROR — tz_locations.md / tz_logging.md.

Sink ``jsonValidation`` / ``resolve``. Does not reject import.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

REASON_FOOTPRINT = "footprint"
REASON_DECLARATION_ORDER = "declaration_order"


def log_settlement_volume_separation(
    *,
    winner_uid: str,
    loser_uid: str,
    winner_name: str | None,
    loser_name: str | None,
    winner_subtype: str | None,
    loser_subtype: str | None,
    winner_size: str,
    loser_size: str,
    winner_side_fine: int,
    loser_side_fine: int,
    winner_map_z: int,
    loser_map_z: int,
    winner_z0: int,
    winner_z1: int,
    loser_z0: int,
    loser_z1: int,
    empty_x: int,
    empty_y: int,
    empty_z: int,
    min_xy: int,
    min_z: int,
    reason: str,
) -> None:
    extra: dict[str, Any] = {
        "activity": "settlement_volume_separation",
        "winner_uid": winner_uid,
        "loser_uid": loser_uid,
        "winner_name": winner_name,
        "loser_name": loser_name,
        "winner_subtype": winner_subtype,
        "loser_subtype": loser_subtype,
        "winner_size": winner_size,
        "loser_size": loser_size,
        "winner_side_fine": winner_side_fine,
        "loser_side_fine": loser_side_fine,
        "winner_map_z": winner_map_z,
        "loser_map_z": loser_map_z,
        "winner_z0": winner_z0,
        "winner_z1": winner_z1,
        "loser_z0": loser_z0,
        "loser_z1": loser_z1,
        "empty_x": empty_x,
        "empty_y": empty_y,
        "empty_z": empty_z,
        "min_xy": min_xy,
        "min_z": min_z,
        "reason": reason,
    }
    logger.error(
        "json_validation | settlement_volume_separation "
        "winner=%s loser=%s reason=%s "
        "size=%s/%s side=%s vs %s/%s side=%s "
        "map_z=%s volume_z=[%s,%s] vs map_z=%s volume_z=[%s,%s] "
        "empty_x=%s empty_y=%s empty_z=%s min_xy=%s min_z=%s",
        winner_uid,
        loser_uid,
        reason,
        winner_subtype,
        winner_size,
        winner_side_fine,
        loser_subtype,
        loser_size,
        loser_side_fine,
        winner_map_z,
        winner_z0,
        winner_z1,
        loser_map_z,
        loser_z0,
        loser_z1,
        empty_x,
        empty_y,
        empty_z,
        min_xy,
        min_z,
        extra=extra,
    )
