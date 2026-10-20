"""Physical basin profile, independent of cell roles and location identity."""

from enum import StrEnum


class BasinKind(StrEnum):
    SEA = "sea"
    OCEAN = "ocean"
    INLAND_SEA = "inland_sea"
    LAKE = "lake"
