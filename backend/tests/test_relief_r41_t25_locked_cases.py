"""LOCKED occupancy / mill cases — R41-T-25.

Do not change maps, assertions, or delete tests without an explicit user request.

leftover_plus_halo (не шов макротайлов C29): клетки leftover SLOPE/SHEER в sidecar
плюс их 8-соседи, которые есть в ``z_height_map`` этого bake. Не все равнины
тайла. Валидатор ходит только по этим клеткам.

SoT: ``docs/tz_terrain_relief.md`` R41-T-25; consume R44.
"""

from __future__ import annotations

import unittest
from collections.abc import Callable
from unittest.mock import patch

from app.application.worldData.generators.terrain.relief.discover.core import (
    discover_fronts,
)
from app.application.worldData.generators.terrain.relief.discover.packSenders import (
    walk_pack_senders,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    OpenLandPlugin,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    FrontGeometry,
)
from app.application.worldData.generators.terrain.relief.sample.openLandTerrains import (
    open_land_terrain_keys,
)
from app.application.worldData.generators.terrain.relief.validate.gradeCellRays import (
    leftover_plus_halo,
    validate_grade_cell_empty_rays,
)
from app.application.worldData.pack.refine.gradeRimRays import pack_slots_for_persist
from app.application.worldData.pack.refine.meterGradeSurface import MeterGradeSurface
from app.dataModel.spatial.facing import Facing, GRID_OUTWARD_DELTA
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.gradeRimRay import (
    GradeRimRay,
    couple_rim_rays,
    merge_grade_rim_rays,
    pack_rim_slot_rays,
)
from app.dataModel.terrain.relief.reliefTerrainEnvelope import ReliefOntologyEnvelopes
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks


def _rect_z(
    width: int,
    height: int,
    at: Callable[[int, int], int],
) -> dict[tuple[int, int], int]:
    return {(x, y): at(x, y) for x in range(width) for y in range(height)}


def _has_eight_neighbors(
    cell: tuple[int, int],
    z_height_map: dict[tuple[int, int], int],
) -> bool:
    x, y = cell
    return all(
        (x + dx, y + dy) in z_height_map
        for dx, dy in GRID_OUTWARD_DELTA.values()
    )


def _leftover_from_fronts(
    fronts: tuple[FrontGeometry, ...],
) -> tuple[GradeRimRay, ...]:
    plains = ReliefOntologyEnvelopes.canonical_defaults().plains
    acc: list[GradeRimRay] = []
    for front in fronts:
        outcome = plains.slope_outcome(abs(int(front.first_dz)), 1)
        if outcome == "skip":
            continue
        kind = (
            ReliefSideKind.SLOPE if outcome == "slope" else ReliefSideKind.SHEER
        )
        acc.extend(
            GradeRimRay(x=int(x), y=int(y), facing=facing, kind=kind)
            for (x, y), facing in walk_pack_senders(
                front.rim, front.corridor, front.outward,
            )
        )
    return merge_grade_rim_rays(acc)


def _discover_open_land(z: dict[tuple[int, int], int]) -> tuple[FrontGeometry, ...]:
    plains = WorldTerrainMasks.canonical_defaults().default_plains.system_terrain
    xs = [x for x, _y in z]
    ys = [y for _x, y in z]
    surface = MeterGradeSurface(
        surface_z=z,
        surface_terrain={xy: plains for xy in z},
        hydrology=None,
        surface_facing=None,
    )
    result = discover_fronts(
        surface,
        origin_x=min(xs),
        origin_y=min(ys),
        width=max(xs) - min(xs) + 1,
        height=max(ys) - min(ys) + 1,
        plugins=(OpenLandPlugin(open_land_terrain_keys()),),
        cell_blocked=lambda _xy: False,
    )
    return result.fronts


def _assert_pack_closes_interior(
    test: unittest.TestCase,
    slots: tuple[GradeRimRay, ...],
    halo: tuple[tuple[int, int], ...],
    z: dict[tuple[int, int], int],
    *interior: tuple[int, int],
) -> None:
    for cell in interior:
        test.assertTrue(_has_eight_neighbors(cell, z), cell)
        present = {ray.facing for ray in slots if ray.cell == cell}
        test.assertEqual(present, set(Facing), cell)
    with patch(
        "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
    ) as err:
        n_empty = validate_grade_cell_empty_rays(
            halo, slots, z_height_map=z,
        )
    err.assert_not_called()
    test.assertEqual(n_empty, 0)


class TestLockedLeftoverPlusHalo(unittest.TestCase):
    """leftover origin + 8-halo в этом heightmap. Не стык макротайлов."""

    def test_leftover_plus_halo_excludes_far_plains(self) -> None:
        leftover = (
            GradeRimRay(x=1, y=1, facing=Facing.SOUTH, kind=ReliefSideKind.SHEER),
        )
        z = {(x, y): 4 for x in range(5) for y in range(5)}
        uni = set(leftover_plus_halo(leftover, z))
        self.assertIn((1, 1), uni)
        self.assertIn((1, 0), uni)
        self.assertIn((2, 2), uni)
        self.assertNotIn((4, 4), uni)


class TestLockedUnitLedge(unittest.TestCase):
    """Одиночный уступ 4|3 (не дырка 1×1): коридор на первой 3; pack 8 слотов."""

    def test_unit_ledge_corridor_on_lower_and_pack_closes_interior(self) -> None:
        z = _rect_z(6, 3, lambda x, _y: 4 if x <= 2 else 3)
        fronts = _discover_open_land(z)
        east = [f for f in fronts if f.outward is Facing.EAST]
        self.assertTrue(east)
        lower = {xy for xy, zv in z.items() if zv == 3}
        corridor = {xy for f in east for xy in f.corridor}
        self.assertTrue(corridor & lower)
        slots, halo = pack_slots_for_persist(_leftover_from_fronts(fronts), z)
        self.assertTrue(halo)
        _assert_pack_closes_interior(self, slots, halo, z, (2, 1), (3, 1))


class TestLockedOneByOneHole(unittest.TestCase):
    """Дырка 1×1: C41 skip, leftover нет, leftover_plus_halo пустой — не T-15."""

    def test_one_by_one_hole_has_empty_halo(self) -> None:
        z = _rect_z(3, 3, lambda x, y: 2 if (x, y) == (1, 1) else 4)
        fronts = _discover_open_land(z)
        self.assertEqual(fronts, ())
        leftover = _leftover_from_fronts(fronts)
        self.assertEqual(leftover, ())
        slots, halo = pack_slots_for_persist(leftover, z)
        self.assertEqual(halo, ())
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            n_empty = validate_grade_cell_empty_rays(
                halo, slots, z_height_map=z,
            )
        err.assert_not_called()
        self.assertEqual(n_empty, 0)


class TestLockedPeak(unittest.TestCase):
    """Изолированный пик: mill смотрит 8 сторон (не каскад в одну)."""

    def test_isolated_peak_shoots_eight_mill_facings(self) -> None:
        z = _rect_z(3, 3, lambda x, y: 4 if (x, y) == (1, 1) else 2)
        fronts = _discover_open_land(z)
        self.assertEqual({f.outward for f in fronts}, set(Facing))
        slots, halo = pack_slots_for_persist(_leftover_from_fronts(fronts), z)
        _assert_pack_closes_interior(self, slots, halo, z, (1, 1))


class TestLockedStraightFront(unittest.TestCase):
    """Прямой W×L 4|3: mill один EAST, не 8 Instance с кромки."""

    def test_straight_terrace_mill_is_east_only(self) -> None:
        z = _rect_z(6, 3, lambda x, _y: 4 if x <= 2 else 3)
        fronts = _discover_open_land(z)
        from_high = [
            f for f in fronts
            if f.rim and all(z[xy] == 4 for xy in f.rim)
        ]
        self.assertTrue(from_high)
        self.assertEqual({f.outward for f in from_high}, {Facing.EAST})


class TestLockedCascade(unittest.TestCase):
    """Склон в одну сторону: mill SOUTH, не тело×8; pack закрывает интерьер."""

    def test_south_steps_mill_is_south_only_and_pack_closes_interior(self) -> None:
        z = _rect_z(5, 6, lambda _x, y: 2 + y)
        fronts = _discover_open_land(z)
        from_top = [
            f for f in fronts
            if f.rim and all(z[xy] == 7 for xy in f.rim)
        ]
        self.assertTrue(from_top)
        self.assertEqual({f.outward for f in from_top}, {Facing.SOUTH})
        slots, halo = pack_slots_for_persist(_leftover_from_fronts(fronts), z)
        self.assertTrue(halo)
        _assert_pack_closes_interior(self, slots, halo, z, (2, 3), (2, 2))


class TestLockedCouple(unittest.TestCase):
    """Same-z без COUPLE = empty; COUPLE закрывает слот (не закрытие из z)."""

    def test_same_z_without_couple_is_empty(self) -> None:
        z = {(0, 0): 5, (1, 0): 5}
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((0, 0), (1, 0)), (), z_height_map=z)
        self.assertEqual(err.call_count, 2)

    def test_same_z_couple_closes_without_inventing_from_z(self) -> None:
        z = {(0, 0): 5, (1, 0): 5}
        leftover = pack_rim_slot_rays((), cells=set(z))
        halo = ((0, 0), (1, 0))
        rays = couple_rim_rays(halo, leftover, z)
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            n_empty = validate_grade_cell_empty_rays(
                halo, rays, z_height_map=z,
            )
        err.assert_not_called()
        self.assertEqual(n_empty, 0)


if __name__ == "__main__":
    unittest.main()
