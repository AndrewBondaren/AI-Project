"""One `worlds.connection_type_registry[]` row — N1-W-06."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import StrictOnWire


class ConnectionTypeEntry(BaseModel):
    """tz_structure_connections.md §2.1 — edge type vocabulary."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_connection_type: StrictOnWire[str]
    display_name: StrictOnWire[str]
