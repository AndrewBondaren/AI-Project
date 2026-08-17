"""Vertex-body plugins — one construction, context = body (R41).

``shore`` / thick ravine geometry stay TBD (plan layer 5). Ravine here is the
same frame: bank = body, shoot into the mask. Road pavement = body (layer 4).
"""

from __future__ import annotations

from typing import Protocol

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    EIGHT_DELTAS,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    ReliefSurface,
)
from app.dataModel.terrain.relief.enums import ReliefContext


class VertexBodyPlugin(Protocol):
    """Shared plugin signature — filled before the first context pass."""

    context: ReliefContext

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        """Whether a C39 rim at ``xy`` is this context's vertex."""

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        """8-flood may include ``xy`` (same-z checked by core)."""

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        """Outward step from rim ``src`` onto ``dst`` (not into body)."""

    def allows_unit_stamp(self) -> bool:
        """False on open_land: plains/forest ``|dz|=1`` is not a Grade (R37)."""


def _has_lower_terrain(
    xy: Coord,
    surface: ReliefSurface,
    terrain_key: str,
) -> bool:
    z = surface.z_at(xy)
    if z is None:
        return False
    x, y = xy
    key = str(terrain_key)
    for dx, dy in EIGHT_DELTAS:
        nb = (x + dx, y + dy)
        zn = surface.z_at(nb)
        if zn is None or int(zn) >= int(z):
            continue
        if surface.terrain_at(nb) == key:
            return True
    return False


class OpenLandPlugin:
    context = ReliefContext.OPEN_LAND

    def __init__(
        self,
        land_keys: frozenset[str],
        ravine_key: str | None = None,
    ) -> None:
        self._land = land_keys
        self._ravine = str(ravine_key) if ravine_key else None

    def _is_ravine_bank(self, xy: Coord, surface: ReliefSurface) -> bool:
        return (
            self._ravine is not None
            and _has_lower_terrain(xy, surface, self._ravine)
        )

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        terrain = surface.terrain_at(xy)
        if terrain is None or terrain not in self._land:
            return False
        return not self._is_ravine_bank(xy, surface)

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        return self.claims(xy, surface)

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        return surface.z_at(dst) is not None

    def allows_unit_stamp(self) -> bool:
        return False


class RoadShoulderPlugin:
    """Pavement = one vertex; shoot both shoulders, not along the road (R41)."""

    context = ReliefContext.ROAD_SHOULDER

    def __init__(self, road_key: str) -> None:
        self._road = str(road_key)

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        return surface.terrain_at(xy) == self._road

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        return surface.terrain_at(xy) == self._road

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        terrain = surface.terrain_at(dst)
        return terrain is not None and terrain != self._road

    def allows_unit_stamp(self) -> bool:
        return True


class RavinePlugin:
    """Bank (not the mask) = body; shoot into ravine terrain."""

    context = ReliefContext.RAVINE

    def __init__(self, ravine_key: str, road_key: str) -> None:
        self._ravine = str(ravine_key)
        self._road = str(road_key)

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        terrain = surface.terrain_at(xy)
        if terrain is None or terrain == self._ravine or terrain == self._road:
            return False
        return _has_lower_terrain(xy, surface, self._ravine)

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        """Same as claims: bank at the mask, not the whole same-z landmass (R41-T-4)."""
        return self.claims(xy, surface)

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        return surface.terrain_at(dst) == self._ravine

    def allows_unit_stamp(self) -> bool:
        return True


class ShorePlugin:
    """Layer 5 TBD — same protocol, no body yet."""

    context = ReliefContext.SHORE

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        return False

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        return False

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        return False

    def allows_unit_stamp(self) -> bool:
        return True


def plugins_for_keys(
    *,
    land_keys: frozenset[str],
    road_key: str,
    ravine_key: str,
    contexts: frozenset[ReliefContext],
) -> tuple[VertexBodyPlugin, ...]:
    """Priority: road > shore > ravine > open_land. Shore is registered when asked, still TBD."""
    out: list[VertexBodyPlugin] = []
    if ReliefContext.ROAD_SHOULDER in contexts:
        out.append(RoadShoulderPlugin(road_key))
    if ReliefContext.SHORE in contexts:
        out.append(ShorePlugin())
    if ReliefContext.RAVINE in contexts:
        out.append(RavinePlugin(ravine_key, road_key))
    if ReliefContext.OPEN_LAND in contexts:
        ravine_for_open = (
            ravine_key if ReliefContext.RAVINE in contexts else None
        )
        out.append(OpenLandPlugin(land_keys, ravine_key=ravine_for_open))
    return tuple(out)
