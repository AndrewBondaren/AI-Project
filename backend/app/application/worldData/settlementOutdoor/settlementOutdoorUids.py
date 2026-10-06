"""Deterministic uids for outdoor persist — tz_settlement_outdoor extract.

Typed wrappers over ``worldData/ids`` (project_data_storage_tz § DET-1):
they fix *which* keys are required; the formula lives in the helper only.
"""

from __future__ import annotations

from app.application.worldData.ids import UidKind, entity_uid
from app.dataModel.spatial.facing import Facing


def district_location_uid(
    world_uid: str, settlement_uid: str, system_name: str, index: int,
) -> str:
    return entity_uid(
        world_uid, UidKind.DISTRICT,
        parent=settlement_uid, name=system_name, index=index,
    )


def city_connection_node_uid(
    world_uid: str, settlement_uid: str, tag: str, x: int, y: int, z: int,
) -> str:
    return entity_uid(
        world_uid, UidKind.CITY_NODE,
        parent=settlement_uid, tag=tag, x=x, y=y, z=z,
    )


def district_connection_node_uid(
    world_uid: str, tag: str, x: int, y: int, z: int,
) -> str:
    return entity_uid(
        world_uid, UidKind.CONN_NODE,
        tag=tag, x=x, y=y, z=z,
    )


def area_uid(
    world_uid: str, district_uid: str, min_x: int, min_y: int, facing: Facing,
) -> str:
    return entity_uid(
        world_uid, UidKind.AREA,
        parent=district_uid, min_x=min_x, min_y=min_y, facing=facing,
    )


def building_location_uid(
    world_uid: str, area_uid: str, template_name: str, map_x: int, map_y: int,
) -> str:
    return entity_uid(
        world_uid, UidKind.BUILDING,
        parent=area_uid, template=template_name, map_x=map_x, map_y=map_y,
    )


def level_uid(world_uid: str, building_uid: str, z_offset: int) -> str:
    """Minted once at structure generation (D3) — extract keeps it."""
    return entity_uid(
        world_uid, UidKind.LEVEL, parent=building_uid, z_offset=z_offset,
    )
