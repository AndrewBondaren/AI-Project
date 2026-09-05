"""CITY-T-2c — per-footprint-cell RNG. Not pack tile, not ``city_size``."""

from __future__ import annotations

import random
from enum import StrEnum


class SettlementCellRngRole(StrEnum):
    BUILDINGS = "buildings"
    DISTRICTS = "districts"


def settlement_cell_rng(
    world_uid: str,
    location_uid: str,
    cell_x: int,
    cell_y: int,
    role: SettlementCellRngRole | str,
) -> random.Random:
    suffix = SettlementCellRngRole(role).value
    return random.Random(f"{world_uid}_{location_uid}_{cell_x}_{cell_y}_{suffix}")
