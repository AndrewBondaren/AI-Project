"""Vertex-body plugins — one construction, context = body (R41).

Ravine: land bank + same-z mask walls; shoot into the mask. Flat floor is
not a site. Kind (SLOPE/SHEER) is template knobs via ``grade_constrained``.
Shore: land bank + strip walls; channel bed iff envelope ``grades_channel_bed``.
L/θ stay on the envelope (FrontStage / ``grade_constrained``), not literals here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    EIGHT_DELTAS,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    ReliefSurface,
)
from app.application.worldData.generators.terrain.relief.sample.terrainMap import (
    map_system_terrain,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain, ReliefContext
from app.dataModel.terrain.relief.reliefTerrainEnvelope import (
    ReliefOntologyEnvelopes,
    ReliefTerrainEnvelope,
)


class VertexBodyPlugin(Protocol):
    """Shared plugin signature — filled before the first context pass."""

    context: ReliefContext

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        """Whether a C39 rim at ``xy`` is this context's vertex."""

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        """8-flood may include ``xy`` (same-z checked by core)."""

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        """Outward step from rim ``src`` onto ``dst`` (not into body)."""

    def accept_flood(
        self,
        body: dict[Coord, int],
        surface: ReliefSurface,
    ) -> bool:
        """Keep this same-z flood as a vertex (terrace floor lives on the envelope)."""


def _hydro_entry(surface: ReliefSurface, xy: Coord) -> MapCellHydrology | None:
    return surface.hydro_at(xy)


def _is_shore_strip(xy: Coord, surface: ReliefSurface) -> bool:
    mapped = map_system_terrain(surface.terrain_at(xy))
    if mapped is not None and mapped.is_shore_class():
        return True
    return surface.hydro_role_at(xy) is HydrologyCellRole.SHORE


def _is_open_water_or_bed(xy: Coord, surface: ReliefSurface) -> bool:
    role = surface.hydro_role_at(xy)
    return role is not None and role.blocks_grade_seed()


def _is_river_bed(xy: Coord, surface: ReliefSurface) -> bool:
    return surface.hydro_role_at(xy) is HydrologyCellRole.RIVER_BED


def _shore_kind_at(xy: Coord, surface: ReliefSurface) -> HydrologyShoreKind | None:
    entry = _hydro_entry(surface, xy)
    if entry is not None and entry.shore_kind is not None:
        return entry.shore_kind
    return HydrologyShoreKind.for_open_water_role(surface.hydro_role_at(xy))


def shore_condition_at(
    xy: Coord,
    surface: ReliefSurface,
) -> ReliefConditionTerrain | None:
    """Envelope class from painted shore_* or hydro kind — does not paint cells.

    ``hydrology_role`` is not the envelope key (R37). River bed without
    ``shore_kind`` defaults to ``shore_river`` (U15 bands are not cut yet).
    """
    mapped = map_system_terrain(surface.terrain_at(xy))
    if mapped is not None and mapped.is_shore_class():
        return mapped
    kind = _shore_kind_at(xy, surface)
    if kind is not None:
        return kind.condition_terrain()
    x, y = xy
    river_near = _is_river_bed(xy, surface)
    for dx, dy in EIGHT_DELTAS:
        nb = (x + dx, y + dy)
        mapped_n = map_system_terrain(surface.terrain_at(nb))
        if mapped_n is not None and mapped_n.is_shore_class():
            return mapped_n
        kind_n = _shore_kind_at(nb, surface)
        if kind_n is not None:
            return kind_n.condition_terrain()
        river_near = river_near or _is_river_bed(nb, surface)
    if river_near:
        return ReliefConditionTerrain.SHORE_RIVER
    return None


def _has_lower_cell(xy: Coord, surface: ReliefSurface) -> bool:
    z = surface.z_height_map(xy)
    if z is None:
        return False
    x, y = xy
    height = int(z)
    for dx, dy in EIGHT_DELTAS:
        zn = surface.z_height_map((x + dx, y + dy))
        if zn is not None and int(zn) < height:
            return True
    return False


def _has_lower_match(
    xy: Coord,
    surface: ReliefSurface,
    pred: Callable[[Coord, ReliefSurface], bool],
) -> bool:
    z = surface.z_height_map(xy)
    if z is None:
        return False
    x, y = xy
    for dx, dy in EIGHT_DELTAS:
        nb = (x + dx, y + dy)
        zn = surface.z_height_map(nb)
        if zn is None or int(zn) >= int(z):
            continue
        if pred(nb, surface):
            return True
    return False


def _has_lower_terrain(
    xy: Coord,
    surface: ReliefSurface,
    terrain_key: str,
) -> bool:
    key = str(terrain_key)
    return _has_lower_match(
        xy, surface, lambda nb, surf: surf.terrain_at(nb) == key,
    )


def _is_shore_bank(xy: Coord, surface: ReliefSurface, road_key: str) -> bool:
    terrain = surface.terrain_at(xy)
    if terrain is None or terrain == road_key:
        return False
    if _is_shore_strip(xy, surface) or _is_open_water_or_bed(xy, surface):
        return False
    return _has_lower_match(
        xy,
        surface,
        lambda nb, surf: _is_shore_strip(nb, surf) or _is_open_water_or_bed(nb, surf),
    )


class OpenLandPlugin:
    context = ReliefContext.OPEN_LAND

    def __init__(
        self,
        land_keys: frozenset[str],
        ravine_key: str | None = None,
        *,
        shore_banks: bool = False,
        road_key: str | None = None,
    ) -> None:
        self._land = land_keys
        self._ravine = str(ravine_key) if ravine_key else None
        self._shore_banks = bool(shore_banks)
        self._road = str(road_key) if road_key else ""

    def _is_ravine_bank(self, xy: Coord, surface: ReliefSurface) -> bool:
        return (
            self._ravine is not None
            and _has_lower_terrain(xy, surface, self._ravine)
        )

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        terrain = surface.terrain_at(xy)
        if terrain is None or terrain not in self._land:
            return False
        if self._shore_banks:
            if _is_shore_strip(xy, surface):
                return False
            if _is_shore_bank(xy, surface, self._road):
                return False
        return not self._is_ravine_bank(xy, surface)

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        return self.claims(xy, surface)

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        if surface.z_height_map(dst) is None:
            return False
        if _is_open_water_or_bed(dst, surface):
            return False
        if self._shore_banks and _is_shore_strip(dst, surface):
            return False
        return True

    def accept_flood(
        self,
        body: dict[Coord, int],
        surface: ReliefSurface,
    ) -> bool:
        return bool(body)


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
        if terrain is None or terrain == self._road:
            return False
        return not _is_open_water_or_bed(dst, surface)

    def accept_flood(
        self,
        body: dict[Coord, int],
        surface: ReliefSurface,
    ) -> bool:
        return bool(body)


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

    def accept_flood(
        self,
        body: dict[Coord, int],
        surface: ReliefSurface,
    ) -> bool:
        return bool(body)


class ShorePlugin:
    """Land bank + hydro strip walls; shoot down. Bed iff ``grades_channel_bed``."""

    context = ReliefContext.SHORE

    def __init__(
        self,
        road_key: str,
        *,
        envelopes: ReliefOntologyEnvelopes | None = None,
    ) -> None:
        self._road = str(road_key)
        self._envelopes = envelopes or ReliefOntologyEnvelopes.canonical_defaults()

    def _envelope(self, xy: Coord, surface: ReliefSurface) -> ReliefTerrainEnvelope:
        cls = shore_condition_at(xy, surface)
        if cls is None:
            return ReliefTerrainEnvelope()
        return self._envelopes.for_terrain(cls)

    def _grades_bed(self, xy: Coord, surface: ReliefSurface) -> bool:
        return bool(self._envelope(xy, surface).grades_channel_bed)

    def _is_bank(self, xy: Coord, surface: ReliefSurface) -> bool:
        return _is_shore_bank(xy, surface, self._road)

    def claims(self, xy: Coord, surface: ReliefSurface) -> bool:
        if _is_shore_strip(xy, surface):
            return _has_lower_cell(xy, surface)
        if _is_open_water_or_bed(xy, surface) and self._grades_bed(xy, surface):
            return _has_lower_cell(xy, surface)
        return self._is_bank(xy, surface)

    def flood_member(self, xy: Coord, z_body: int, surface: ReliefSurface) -> bool:
        if surface.terrain_at(xy) == self._road:
            return False
        if _is_shore_strip(xy, surface):
            return True
        if _is_open_water_or_bed(xy, surface) and self._grades_bed(xy, surface):
            return True
        return self._is_bank(xy, surface)

    def may_shoot(self, src: Coord, dst: Coord, surface: ReliefSurface) -> bool:
        if _is_shore_strip(dst, surface):
            return True
        if not _is_open_water_or_bed(dst, surface):
            return False
        return self._grades_bed(src, surface) or self._grades_bed(dst, surface)

    def accept_flood(
        self,
        body: dict[Coord, int],
        surface: ReliefSurface,
    ) -> bool:
        if not body:
            return False
        if any(self._is_bank(xy, surface) for xy in body):
            return True
        xy0 = next(iter(body))
        min_t = self._envelope(xy0, surface).sheer_terrace_min_cells
        if min_t is None:
            return True
        return len(body) >= int(min_t)


def plugins_for_keys(
    *,
    land_keys: frozenset[str],
    road_key: str,
    ravine_key: str,
    contexts: frozenset[ReliefContext],
    envelopes: ReliefOntologyEnvelopes | None = None,
) -> tuple[VertexBodyPlugin, ...]:
    """Priority: road > shore > ravine > open_land. Mountain is outside discover."""
    out: list[VertexBodyPlugin] = []
    if ReliefContext.ROAD_SHOULDER in contexts:
        out.append(RoadShoulderPlugin(road_key))
    if ReliefContext.SHORE in contexts:
        out.append(ShorePlugin(road_key, envelopes=envelopes))
    if ReliefContext.RAVINE in contexts:
        out.append(RavinePlugin(ravine_key, road_key))
    if ReliefContext.OPEN_LAND in contexts:
        ravine_for_open = (
            ravine_key if ReliefContext.RAVINE in contexts else None
        )
        out.append(
            OpenLandPlugin(
                land_keys,
                ravine_key=ravine_for_open,
                shore_banks=ReliefContext.SHORE in contexts,
                road_key=road_key,
            ),
        )
    return tuple(out)
