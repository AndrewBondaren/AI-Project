"""River declare geometry mode — wire enum."""

from __future__ import annotations

from enum import StrEnum


class RiverDeclareMode(StrEnum):
    ENDPOINTS = "endpoints"
    VIA_LOCATIONS = "via_locations"
    SEGMENTS = "segments"
