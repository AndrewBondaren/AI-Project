"""Shared connection defaults: sidewalk, lanes — district + city entry edges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.jsonValidation import road_settings
from app.dataModel.roads.roadSettingsEntry import RoadSettingsEntry
from app.dataModel.roads.worldRoadSettings import WorldRoadSettings
from app.dataModel.settlement.district.districtConnection import (
    DistrictConnection,
    primary_or_default,
)
from app.dataModel.settlement.enums.districtStreetRole import DistrictStreetRole

_FALLBACK_ROAD = RoadSettingsEntry.fallback()


@dataclass(frozen=True)
class ConnectionPaint:
    """Resolved type / lanes / sidewalk / role for one district street class."""

    connection_type: str
    lanes_per_side: int
    has_sidewalk: bool
    role: DistrictStreetRole | None


def primary_connection(template: Any) -> DistrictConnection:
    """Primary district template connection — dataModel ``DistrictConnection``."""
    return primary_or_default(template)


def _road_settings(world: Any | None) -> WorldRoadSettings:
    if world is None:
        return WorldRoadSettings.canonical_defaults()
    return road_settings(world)


def _road_entry(world: Any | None, connection_type: str) -> RoadSettingsEntry | None:
    return _road_settings(world).entry_for(connection_type)


def sidewalk_of(
    conn: DistrictConnection,
    connection_type: str | None = None,
    *,
    world: Any | None = None,
) -> bool:
    ct = connection_type or conn.connection_type
    if conn.sidewalk is not None:
        return bool(conn.sidewalk)
    entry = _road_entry(world, ct)
    if entry is not None:
        return bool(entry.auto_sidewalk)
    return bool(_FALLBACK_ROAD.auto_sidewalk)


def lanes_of(
    conn: DistrictConnection,
    connection_type: str | None = None,
    *,
    world: Any | None = None,
) -> int:
    ct = connection_type or conn.connection_type
    if conn.lanes_per_side is not None:
        return int(conn.lanes_per_side)
    entry = _road_entry(world, ct)
    if entry is not None and entry.default_lanes_per_side is not None:
        return int(entry.default_lanes_per_side)
    return int(_FALLBACK_ROAD.default_lanes_per_side)


def paint_for_connection(
    conn: DistrictConnection,
    *,
    world: Any | None = None,
) -> ConnectionPaint:
    ct = str(conn.connection_type)
    return ConnectionPaint(
        connection_type=ct,
        lanes_per_side=lanes_of(conn, ct, world=world),
        has_sidewalk=sidewalk_of(conn, ct, world=world),
        role=DistrictStreetRole.from_wire(conn.role),
    )


def resolve_has_sidewalk(
    template: Any,
    connection_type: str | None = None,
    *,
    world: Any | None = None,
) -> bool:
    """
    has_sidewalk для district/city edges.
    Приоритет: connection.sidewalk → road_settings.auto_sidewalk → fallback.
    """
    return sidewalk_of(
        primary_or_default(template), connection_type, world=world,
    )


def resolve_lanes_per_side(
    template: Any,
    connection_type: str | None = None,
    *,
    world: Any | None = None,
) -> int:
    return lanes_of(primary_or_default(template), connection_type, world=world)
