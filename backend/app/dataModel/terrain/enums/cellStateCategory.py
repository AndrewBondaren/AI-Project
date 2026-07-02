"""Wire `state_category` on terrain/cell states — tz_locations.md."""

from __future__ import annotations

from enum import StrEnum

#Todo think about this enum
class CellStateCategory(StrEnum):
    INTERACTIVE = "interactive"
    ENVIRONMENTAL = "environmental"
