"""Wire `system_gender` — ENUM-E E-22, tz_races.md."""

from __future__ import annotations

from enum import StrEnum


class SystemGender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    ASEXUAL = "asexual"
    BOTH = "both"
