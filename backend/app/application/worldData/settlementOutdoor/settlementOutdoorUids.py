"""Deterministic uids for outdoor persist — tz_settlement_outdoor extract."""

from __future__ import annotations

import uuid

from app.dataModel.locations.enums.entryRole import EntryRole
from app.dataModel.spatial.facing import Facing


def _uuid5(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


def district_location_uid(settlement_uid: str, system_name: str, index: int) -> str:
    return _uuid5(settlement_uid, f"district|{system_name}|{index}")


def area_uid(district_uid: str, min_x: int, min_y: int, facing: Facing) -> str:
    return _uuid5(district_uid, f"area|{min_x}|{min_y}|{facing.value}")


def building_location_uid(
    area_uid: str, template_name: str, map_x: int, map_y: int,
) -> str:
    return _uuid5(area_uid, f"building|{template_name}|{map_x}|{map_y}")


def level_uid(building_uid: str, z: int) -> str:
    return _uuid5(building_uid, f"level_z|{z}")


def entry_uid(building_uid: str, role: EntryRole, passage_uid: str) -> str:
    return _uuid5(building_uid, f"entry|{role.value}|{passage_uid}")
