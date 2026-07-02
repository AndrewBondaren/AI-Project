"""Wire `border_category` on location subtypes — tz_locations.md."""

from __future__ import annotations

from enum import StrEnum

#Todo think about this enum
class BorderCategory(StrEnum):
    LIQUID = "liquid"
    NULL = "null"
