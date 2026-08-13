"""Meter-grid read/write adapter for detailed grade generate — R36u."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.facing import Facing

Coord = tuple[int, int]

# Fine roles matching L0 PRESERVE_HYDROLOGY_ROLES (sea/lake/river) — not SHORE.
_PRESERVE_FINE_HYDRO: frozenset[HydrologyCellRole] = frozenset({
    HydrologyCellRole.COASTAL_SEA,
    HydrologyCellRole.OPEN_OCEAN,
    HydrologyCellRole.INLAND_SEA,
    HydrologyCellRole.LAKE,
    HydrologyCellRole.RIVER_BED,
})



@dataclass
class MeterGradeSurface:
    """Fine-tile meter columns for relief sample + uid stamp (no z mutation)."""

    surface_z: dict[Coord, int]
    surface_terrain: dict[Coord, str]
    hydrology: dict[Coord, MapCellHydrology] | None
    surface_facing: dict[Coord, Facing] | None
    grade_uid: dict[Coord, str] = field(default_factory=dict)

    @classmethod
    def from_tile_surface_state(cls, state: TileSurfaceState) -> MeterGradeSurface:
        terrain = state.surface_terrain or {}
        return cls(
            surface_z=dict(state.heightmap.surface_z),
            surface_terrain=dict(terrain),
            hydrology=dict(state.hydrology) if state.hydrology else None,
            surface_facing=dict(state.surface_facing) if state.surface_facing else None,
            grade_uid=dict(state.surface_grade_uid or {}),
        )

    def z_at(self, xy: Coord) -> int | None:
        return self.surface_z.get(xy)

    def terrain_at(self, xy: Coord) -> str | None:
        return self.surface_terrain.get(xy)

    def hydro_role_at(self, xy: Coord) -> HydrologyCellRole | None:
        if not self.hydrology:
            return None
        entry = self.hydrology.get(xy)
        return None if entry is None else entry.role

    def has_grade(self, xy: Coord) -> bool:
        return bool(self.grade_uid.get(xy))

    def stamp_grade(self, xy: Coord, uid: str) -> None:
        self.grade_uid[xy] = uid


def meter_seed_blocked(
    surface: MeterGradeSurface,
    xy: Coord,
    *,
    road_key: str,
) -> bool:
    terrain = surface.terrain_at(xy)
    if not terrain:
        return True
    if terrain == road_key:
        return True
    if surface.has_grade(xy):
        return True
    role = surface.hydro_role_at(xy)
    if role is not None and role in _PRESERVE_FINE_HYDRO:
        return True
    return False


def meter_grade_cell_blocked(
    surface: MeterGradeSurface,
    xy: Coord,
    *,
    road_key: str,
    barrier_keys: frozenset[str],
) -> bool:
    """Clearance adapter for meter ribbon (R36m / R36u-T-9 residual).

    Mirrors L0 ``cell_blocked_light`` spirit: missing column, already graded,
    other road, open-water hydro, barrier terrain. Footprint ``ref_cells`` are
    handled by ``is_grade_obstacle_light``, not here.
    """
    if surface.z_at(xy) is None:
        return True
    if surface.has_grade(xy):
        return True
    terrain = surface.terrain_at(xy)
    if terrain == road_key:
        return True
    if terrain is not None and terrain in barrier_keys:
        return True
    role = surface.hydro_role_at(xy)
    if role is not None and role in _PRESERVE_FINE_HYDRO:
        return True
    return False
