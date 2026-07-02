"""District template `connections[]` item — tz_city_generation.md §9.5.1."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire

# Builtin district street default — all canonical templates use ``road``.
DEFAULT_CONNECTION_TYPE = "road"


class DistrictConnection(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    connection_type: StrictOnWire[str]
    role: OptionalOnWire[str | None] = None
    sidewalk: OptionalOnWire[bool | None] = None
    lanes_per_side: OptionalOnWire[int | None] = None

    @classmethod
    def street_default(cls) -> DistrictConnection:
        """Primary connection when template omits ``connections[]``."""
        return cls(connection_type=DEFAULT_CONNECTION_TYPE)


def parse_district_connection(raw: Any) -> DistrictConnection | None:
    if isinstance(raw, DistrictConnection):
        return raw
    if isinstance(raw, dict):
        return DistrictConnection.model_validate(raw)
    return None


def primary_from_template(template: Any) -> DistrictConnection | None:
    """First ``connections[]`` row when present and valid."""
    from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry

    if isinstance(template, DistrictTemplateEntry):
        connections = template.connections
        if not connections:
            return None
        return connections[0]
    connections = template.get("connections")
    if not connections:
        return None
    return parse_district_connection(connections[0])


def primary_or_default(template: Any) -> DistrictConnection:
    return primary_from_template(template) or DistrictConnection.street_default()
