"""Meter-grid read/write adapter for detailed grade generate — R36u."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.facing import Facing

Coord = tuple[int, int]


@dataclass
class MeterGradeSurface:
    """Fine-tile meter columns for relief sample + uid stamp (no z mutation).

    ``from_tile_surface_state(alias_heights=True)`` aliases z/terrain/hydro;
    ``grade_uid`` is always a new dict (R36v-T-7).
    """

    surface_z: dict[Coord, int]
    surface_terrain: dict[Coord, str]
    hydrology: dict[Coord, MapCellHydrology] | None
    surface_facing: dict[Coord, Facing] | None
    grade_uid: dict[Coord, str] = field(default_factory=dict)

    @classmethod
    def from_tile_surface_state(
        cls,
        state: TileSurfaceState,
        *,
        alias_heights: bool = False,
    ) -> MeterGradeSurface:
        terrain = state.surface_terrain or {}
        if alias_heights:
            return cls(
                surface_z=state.heightmap.surface_z,
                surface_terrain=terrain,
                hydrology=state.hydrology,
                surface_facing=state.surface_facing,
                grade_uid=dict(state.surface_grade_uid or {}),
            )
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


def _road_grade_or_hydro_blocked(
    surface: MeterGradeSurface,
    xy: Coord,
    *,
    road_key: str,
    barrier_keys: frozenset[str] | None = None,
    ignore_grade: bool = False,
) -> bool:
    if not ignore_grade and surface.has_grade(xy):
        return True
    terrain = surface.terrain_at(xy)
    if terrain == road_key:
        return True
    if barrier_keys is not None and terrain is not None and terrain in barrier_keys:
        return True
    role = surface.hydro_role_at(xy)
    return role is not None and role.blocks_grade_seed()


def meter_seed_blocked(
    surface: MeterGradeSurface,
    xy: Coord,
    *,
    road_key: str,
    ignore_grade: bool = False,
) -> bool:
    """Hard blocks for a seed cell. ``ignore_grade`` keeps stamped halo in land."""
    terrain = surface.terrain_at(xy)
    if not terrain:
        return True
    return _road_grade_or_hydro_blocked(
        surface, xy, road_key=road_key, ignore_grade=ignore_grade,
    )


def meter_grade_cell_blocked(
    surface: MeterGradeSurface,
    xy: Coord,
    *,
    road_key: str,
    barrier_keys: frozenset[str],
) -> bool:
    """Clearance adapter for meter ribbon (R36m / R36u-T-9 residual)."""
    if surface.z_at(xy) is None:
        return True
    return _road_grade_or_hydro_blocked(
        surface, xy, road_key=road_key, barrier_keys=barrier_keys,
    )
