"""Shared connection defaults: sidewalk, lanes — district + city entry edges."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.masterData import road_settings
from app.dataModel.roads.roadSettingsEntry import RoadSettingsEntry
from app.dataModel.roads.worldRoadSettings import WorldRoadSettings

_DEFAULT_LANES_PER_SIDE = 1
_DEFAULT_AUTO_SIDEWALK = False


def primary_connection(template: dict) -> dict:
    connections = template.get("connections") or []
    return connections[0] if connections else {}


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
    Приоритет: connections[0].sidewalk → road_settings.auto_sidewalk → False.
    """
    primary = primary_connection(template)
    ct = connection_type or primary.get("connection_type") or "road"
    sidewalk_decl = primary.get("sidewalk")
    if sidewalk_decl is not None:
        return bool(sidewalk_decl)
    entry = _road_entry(world, ct)
    if entry is not None:
        return bool(entry.auto_sidewalk)
    return _DEFAULT_AUTO_SIDEWALK


def resolve_lanes_per_side(
    template: dict,
    connection_type: str | None = None,
    *,
    world: Any | None = None,
) -> int:
    primary = primary_connection(template)
    ct = connection_type or primary.get("connection_type") or "road"
    lanes_decl = primary.get("lanes_per_side")
    if lanes_decl is not None:
        return int(lanes_decl)
    entry = _road_entry(world, ct)
    if entry is not None and entry.default_lanes_per_side is not None:
        return int(entry.default_lanes_per_side)
    return _DEFAULT_LANES_PER_SIDE
