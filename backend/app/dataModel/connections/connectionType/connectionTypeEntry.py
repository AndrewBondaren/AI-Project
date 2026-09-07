"""One `worlds.connection_type_registry[]` row — N1-W-06."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.registryKey import RegistryKey

if TYPE_CHECKING:
    from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
        WorldConnectionTypeRegistry,
    )


class ConnectionTypeEntry(BaseModel):
    """tz_structure_connections.md §2.1 — edge type vocabulary."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_connection_type: StrictOnWire[RegistryKey[WorldConnectionTypeRegistry]]
    display_name: StrictOnWire[str]
