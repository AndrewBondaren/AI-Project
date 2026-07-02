"""Wire bridge subtype keys."""

from __future__ import annotations

from enum import StrEnum

#Not used yet in the generator.
class BridgeSubtype(StrEnum):
    PEDESTRIAN = "pedestrian"
    TRANSPORT = "transport"
    VIADUCT = "viaduct"
