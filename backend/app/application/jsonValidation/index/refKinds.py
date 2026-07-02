"""REF-W cross-reference kinds — ``docs/tz_json_validation.md`` § REF-W → N1-W."""

from __future__ import annotations

from enum import StrEnum


class RefKind(StrEnum):
    MATERIAL = "REF-W-MATERIAL"
    LIQUID = "REF-W-LIQUID"
    TERRAIN = "REF-W-TERRAIN"
    CLIMATE = "REF-W-CLIMATE"
    ECON_TIER = "REF-W-ECON-TIER"
    CONN = "REF-W-CONN"
    LOC_TYPE = "REF-W-LOC-TYPE"
