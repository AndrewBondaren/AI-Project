"""Vertex-body plugins — one construction, context = body (R41).

Ravine: land bank + same-z mask walls; shoot into the mask. Flat floor is
not a site. Kind (SLOPE/SHEER) is template knobs via ``grade_constrained``.
``shore`` stays stub (geometry). Ontology classes: ``shore_river`` /
``shore_mountain_river`` / ``shore_lake`` / ``shore_sea``.
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


def _has_lower_cell(xy: Coord, surface: ReliefSurface) -> bool:
    z = surface.z_at(xy)
    if z is None:
        return False
    x, y = xy
    height = int(z)
    for dx, dy in EIGHT_DELTAS:
        zn = surface.z_at((x + dx, y + dy))
        if zn is not None and int(zn) < height:
            return True
    return False


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


class RavinePlugin:
    """Land bank + ravine-mask walls; shoot into the mask. Floor without Δz is not a site.

    Kind (SLOPE/SHEER) comes from template knobs via ``grade_constrained``, not here.
    """

    context = ReliefContext.RAVINE

    def __init__(self, ravine_key: str, road_key: str) -> None:
        self._ravine = str(ravine_key)
        self._road = str(road_key)

    def _is_mask(self, xy: Coord, surface: ReliefSurface) -> bool:
        return surface.terrain_at(xy) == self._ravine

    def _is_bank(self, xy: Coord, surface: ReliefSurface) -> bool:
        terrain = surface.terrain_at(xy)
        if terrain is None or terrain == self._ravine or terrain == self._road:
            return False
        return _has_lower_terrain(xy, surface, self._ravine)

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        if self._is_mask(xy, surface):
            return _has_lower_cell(xy, surface)
        return self._is_bank(xy, surface)

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        """Mask terrace (incl. interior); bank stays bank-only so plains mesa is not swallowed."""
        if surface.terrain_at(xy) == self._road:
            return False
        if self._is_mask(xy, surface):
            return True
        return self._is_bank(xy, surface)

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        return surface.terrain_at(dst) == self._ravine


class ShorePlugin:
    """Layer 5 TBD — same protocol, no body yet."""

    context = ReliefContext.SHORE

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        return False

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        return False

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        return False


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
