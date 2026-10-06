"""CITY-T-2c — per-footprint-cell RNG. Not pack tile, not ``city_size``."""

from __future__ import annotations

import random
from enum import StrEnum

from app.application.worldData.ids import UidKind, entity_rng


class SettlementCellRngRole(StrEnum):
    BUILDINGS = "buildings"
    DISTRICTS = "districts"
    SUBJECTS = "subjects"


def settlement_cell_rng(
    world_uid: str,
    location_uid: str,
    cell_x: int,
    cell_y: int,
    role: SettlementCellRngRole | str,
) -> random.Random:
    role = SettlementCellRngRole(role)
    return entity_rng(
        world_uid, UidKind.CELL,
        location=location_uid, cell_x=cell_x, cell_y=cell_y, role=role,
    )
