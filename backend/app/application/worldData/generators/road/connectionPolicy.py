"""Shared connection defaults: sidewalk, lanes — district + city entry edges."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation import road_settings
from app.dataModel.roads.roadSettingsEntry import RoadSettingsEntry
from app.dataModel.roads.worldRoadSettings import WorldRoadSettings
from app.dataModel.settlement.district.districtConnection import (
    DistrictConnection,
    primary_or_default,
)

_FALLBACK_ROAD = RoadSettingsEntry.fallback()


def primary_connection(template: dict) -> DistrictConnection:
    """Primary district template connection — dataModel ``DistrictConnection``."""
    return primary_or_default(template)


def _road_settings(world: Any | None) -> WorldRoadSettings:
    if world is None:
        return WorldRoadSettings.canonical_defaults()
    return road_settings(world)


def _road_entry(world: Any | None, connection_type: str) -> RoadSettingsEntry | None:
    return _road_settings(world).entry_for(connection_type)


def resolve_has_sidewalk(
    template: dict,
    connection_type: str | None = None,
    *,
    world: Any | None = None,
) -> bool:
    """
    has_sidewalk для district/city edges.
    Приоритет: connections[0].sidewalk → road_settings.auto_sidewalk → fallback.
    """
    conn = primary_or_default(template)
    ct = connection_type or conn.connection_type
    if conn.sidewalk is not None:
        return bool(conn.sidewalk)
    entry = _road_entry(world, ct)
    if entry is not None:
        return bool(entry.auto_sidewalk)
    return bool(_FALLBACK_ROAD.auto_sidewalk)


def resolve_lanes_per_side(
    template: dict,
    connection_type: str | None = None,
    *,
    world: Any | None = None,
) -> int:
    conn = primary_or_default(template)
    ct = connection_type or conn.connection_type
    if conn.lanes_per_side is not None:
        return int(conn.lanes_per_side)
    entry = _road_entry(world, ct)
    if entry is not None and entry.default_lanes_per_side is not None:
        return int(entry.default_lanes_per_side)
    return int(_FALLBACK_ROAD.default_lanes_per_side)
