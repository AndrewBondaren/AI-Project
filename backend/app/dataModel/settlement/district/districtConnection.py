"""District template `connections[]` item — tz_city_generation.md §9.5.1."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    ConnectionTypeKey,
    WorldConnectionTypeRegistry,
)


def _engine_street_connection_type() -> ConnectionTypeKey:
    return WorldConnectionTypeRegistry.require_engine(
        WorldConnectionTypeRegistry.SYSTEM_CONNECTION_TYPE_ROAD,
    )


# Resolved engine key — not a parallel literal. Canonical templates omit connections[].
DEFAULT_CONNECTION_TYPE = _engine_street_connection_type()


class DistrictConnection(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    connection_type: StrictOnWire[ConnectionTypeKey]
    role: DefaultOnWire[str | None] = None
    sidewalk: DefaultOnWire[bool | None] = None
    lanes_per_side: DefaultOnWire[int | None] = None

    @classmethod
    def street_default(cls) -> DistrictConnection:
        """Primary connection when template omits ``connections[]``."""
        return cls(connection_type=_engine_street_connection_type())


def parse_district_connection(raw: Any) -> DistrictConnection | None:
    if isinstance(raw, DistrictConnection):
        return raw
    if isinstance(raw, dict):
        return DistrictConnection.model_validate(raw)
    return None


def primary_from_template(template: Any) -> DistrictConnection | None:
    """First ``connections[]`` row when present and valid."""
    connections = getattr(template, "connections", None)
    if not connections:
        return None
    first = connections[0]
    if isinstance(first, DistrictConnection):
        return first
    return parse_district_connection(first)


def primary_or_default(template: Any) -> DistrictConnection:
    return primary_from_template(template) or DistrictConnection.street_default()
