"""Wire ``livestock_kind`` — ENUM-E purpose of husbandry. tz_city_generation.md §1.2."""

from __future__ import annotations

from enum import StrEnum


class LivestockKind(StrEnum):
    """Why this animal is raised. N+1 instances are ``system_livestock`` rows."""

    MEAT = "meat"
    DAIRY = "dairy"
    FIBER = "fiber"
    DRAFT = "draft"
    MOUNT = "mount"
