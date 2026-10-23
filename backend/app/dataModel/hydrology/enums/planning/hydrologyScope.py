"""Existing hydrology scope vocabulary and bootstrap subset; no new execution scope."""

from enum import StrEnum


class HydrologyScope(StrEnum):
    COASTAL_SEA = "coastal_sea"
    OPEN_OCEAN = "open_ocean"
    LAKES = "lakes"
    RIVERS = "rivers"
    LANDFORMS = "landforms"


HYDROLOGY_BOOTSTRAP_SCOPES = frozenset({
    HydrologyScope.COASTAL_SEA,
    HydrologyScope.OPEN_OCEAN,
    HydrologyScope.LAKES,
    HydrologyScope.RIVERS,
})
