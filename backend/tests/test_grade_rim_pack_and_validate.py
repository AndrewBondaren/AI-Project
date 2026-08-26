"""Pack rim edge: sender C41 + receiver opposite — tz_terrain_relief_consume."""

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
    DiscoveredFront,
    FrontGeometry,
    GradePaintSpec,
)
from app.application.worldData.generators.terrain.relief.sample.openLandTerrains import (
    open_land_terrain_keys,
)
from app.application.worldData.pack.refine.meterGradeSurface import MeterGradeSurface
from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_GRADE_CELL_EMPTY_RAY,
)
from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    RibbonGradeDecision,
)
from app.application.worldData.generators.terrain.relief.validate.gradeCellRays import (
    leftover_plus_halo,
    validate_grade_cell_empty_rays,
)
from app.application.worldData.pack.refine.gradeRimRays import (
    pack_slots_for_persist,
    rim_rays_from_front,
)
from app.dataModel.spatial.facing import Facing, GRID_OUTWARD_DELTA, opposite
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefSideKind
from app.dataModel.terrain.relief.reliefTerrainEnvelope import ReliefOntologyEnvelopes
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.terrain.relief.gradeRimRay import (
    GradeRimRay,
    couple_rim_rays,
    downhill_leftover_rim_rays,
    merge_grade_rim_rays,
    pack_rim_slot_rays,
    receiver_rim_ray,
)


def _sender(
    x: int = 10,
    y: int = 924,
    facing: Facing = Facing.SOUTH,
    kind: ReliefSideKind = ReliefSideKind.SHEER,
) -> GradeRimRay:
    return GradeRimRay(x=x, y=y, facing=facing, kind=kind)


def _decision(kind: ReliefSideKind = ReliefSideKind.SHEER) -> RibbonGradeDecision:
    return RibbonGradeDecision(
        template_uid="t",
        policy=None,
        kind=kind,
        requested_length=2,
        h=10,
        geom=None,
        earthen_canal=None,
        structure_refs=(),
        reason="unit",
        skipped=False,
    )


def _front(
    *,
    rim: tuple[tuple[int, int], ...] = ((10, 925),),
    corridor: tuple[tuple[int, int], ...] = ((10, 924),),
    outward: Facing = Facing.SOUTH,
    kind: ReliefSideKind = ReliefSideKind.SHEER,
) -> DiscoveredFront:
    return DiscoveredFront(
        spec=GradePaintSpec(
            grade_uid="g",
            outward=outward,
            front_w=len(rim),
            anchor_top=min(rim),
            anchor_bottom=corridor[-1] if corridor else rim[0],
            decision=_decision(kind),
            corridor=corridor,
        ),
        context=ReliefContext.OPEN_LAND,
        site_id="s",
        slot=1,
        template_uid="t",
        rim=rim,
        terrain_key="plains",
        system_terrain="plains",
        dz=20,
    )


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


def _pack_like_persist(
    senders: tuple[GradeRimRay, ...],
    z_height_map: dict[tuple[int, int], int],
) -> tuple[tuple[GradeRimRay, ...], tuple[tuple[int, int], ...]]:
    """Same leftover → downhill fill → COUPLE as ``FineChunkPersist.finish``."""
    return pack_slots_for_persist(senders, z_height_map)


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


def _discover_open_land(
    z: dict[tuple[int, int], int],
) -> tuple[FrontGeometry, ...]:
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


class TestPackRimSlotRays(unittest.TestCase):
    def test_receiver_is_opposite_neighbor(self) -> None:
        sender = _sender()
        recv = receiver_rim_ray(sender)
        self.assertEqual(recv.cell, (10, 923))
        self.assertEqual(recv.facing, Facing.NORTH)
        self.assertEqual(recv.kind, ReliefSideKind.SHEER)
        self.assertEqual(recv.facing, opposite(sender.facing))

    def test_omit_receiver_without_cell(self) -> None:
        sender = _sender()
        slots = pack_rim_slot_rays((sender,), cells={(10, 924)})
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].cell, (10, 924))
        self.assertEqual(slots[0].facing, Facing.SOUTH)

    def test_writes_receiver_when_cell_exists(self) -> None:
        sender = _sender()
        slots = pack_rim_slot_rays((sender,), cells={(10, 924), (10, 923)})
        by = {(r.x, r.y, r.facing): r for r in slots}
        self.assertIn((10, 924, Facing.SOUTH), by)
        self.assertIn((10, 923, Facing.NORTH), by)
        self.assertEqual(by[(10, 923, Facing.NORTH)].kind, ReliefSideKind.SHEER)


class TestMergeGradeRimRays(unittest.TestCase):
    def test_first_wins_keeps_earlier_kind(self) -> None:
        first = GradeRimRay(x=0, y=0, facing=Facing.SOUTH, kind=ReliefSideKind.SLOPE)
        later = GradeRimRay(x=0, y=0, facing=Facing.SOUTH, kind=ReliefSideKind.SHEER)
        couple = GradeRimRay(x=0, y=0, facing=Facing.SOUTH, kind=ReliefSideKind.COUPLE)
        merged = merge_grade_rim_rays((first,), (later, couple))
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].kind, ReliefSideKind.SLOPE)


class TestCoupleRimRays(unittest.TestCase):
    def test_writes_both_ends_and_skips_leftover_slot(self) -> None:
        leftover = (
            GradeRimRay(x=0, y=1, facing=Facing.SOUTH, kind=ReliefSideKind.SLOPE),
        )
        z = {(0, 1): 5, (0, 0): 3, (1, 1): 5}
        halo = leftover_plus_halo(leftover, z)
        couples = couple_rim_rays(halo, leftover, z)
        by = {(r.x, r.y, r.facing): r for r in couples}
        self.assertNotIn((0, 1, Facing.SOUTH), by)
        self.assertEqual(by[(0, 1, Facing.EAST)].kind, ReliefSideKind.COUPLE)
        self.assertEqual(by[(1, 1, Facing.WEST)].kind, ReliefSideKind.COUPLE)
        slots = merge_grade_rim_rays(leftover, couples)
        self.assertEqual(
            {(r.x, r.y, r.facing): r.kind for r in slots}[(0, 1, Facing.SOUTH)],
            ReliefSideKind.SLOPE,
        )

    def test_couples_do_not_grow_leftover_plus_halo(self) -> None:
        leftover = (
            GradeRimRay(x=0, y=0, facing=Facing.EAST, kind=ReliefSideKind.SLOPE),
        )
        z = {(0, 0): 8, (1, 0): 6, (50, 50): 4, (51, 50): 4}
        leftover_slots = pack_rim_slot_rays(leftover, cells=set(z))
        halo = leftover_plus_halo(leftover_slots, z)
        slots = merge_grade_rim_rays(
            leftover_slots,
            couple_rim_rays(halo, leftover_slots, z),
        )
        uni = set(leftover_plus_halo(slots, z))
        self.assertIn((0, 0), uni)
        self.assertIn((1, 0), uni)
        self.assertNotIn((50, 50), uni)
        self.assertNotIn((51, 50), uni)


class TestWalkPackSenders(unittest.TestCase):
    def test_walk_emits_corridor_not_only_rim(self) -> None:
        keys = walk_pack_senders(((10, 925),), ((10, 924),), Facing.SOUTH)
        self.assertIn(((10, 925), Facing.SOUTH), keys)
        self.assertIn(((10, 924), Facing.SOUTH), keys)

    def test_walk_width_equal_z_is_not_pack_sender(self) -> None:
        keys = set(walk_pack_senders(((0, 10), (1, 10)), (), Facing.SOUTH))
        self.assertIn(((0, 10), Facing.SOUTH), keys)
        self.assertIn(((1, 10), Facing.SOUTH), keys)
        self.assertNotIn(((0, 10), Facing.EAST), keys)
        self.assertNotIn(((1, 10), Facing.WEST), keys)

    def test_front_rays_include_corridor_sheer(self) -> None:
        rays = rim_rays_from_front(_front())
        by = {(r.x, r.y, r.facing): r for r in rays}
        self.assertEqual(by[(10, 924, Facing.SOUTH)].kind, ReliefSideKind.SHEER)
        self.assertIn((10, 925, Facing.SOUTH), by)


class TestGradeCellEmptyRayValidator(unittest.TestCase):
    def test_complete_eight_slots_no_error(self) -> None:
        cell = (0, 0)
        rays = tuple(
            GradeRimRay(x=0, y=0, facing=facing, kind=ReliefSideKind.SHEER)
            for facing in Facing
        )
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays((cell,), rays, z_height_map={(0, 0): 1})
        err.assert_not_called()

    def test_isolated_cell_omits_missing_neighbors(self) -> None:
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((0, 0),), (), z_height_map={(0, 0): 1})
        err.assert_not_called()

    def test_same_z_without_pack_couple_is_empty(self) -> None:
        z = {(0, 0): 5, (1, 0): 5}
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((0, 0), (1, 0)), (), z_height_map=z)
        self.assertEqual(err.call_count, 2)
        east = next(c for c in err.call_args_list if c.kwargs["x"] == 0)
        west = next(c for c in err.call_args_list if c.kwargs["x"] == 1)
        self.assertEqual(east.kwargs["open"], "E")
        self.assertEqual(west.kwargs["open"], "W")

    def test_same_z_pack_couple_closes_slot(self) -> None:
        z = {(0, 0): 5, (1, 0): 5}
        rays = (
            GradeRimRay(x=0, y=0, facing=Facing.EAST, kind=ReliefSideKind.COUPLE),
            GradeRimRay(x=1, y=0, facing=Facing.WEST, kind=ReliefSideKind.COUPLE),
        )
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((0, 0), (1, 0)), rays, z_height_map=z)
        err.assert_not_called()

    def test_all_eight_open_when_neighbors_different_z(self) -> None:
        z: dict[tuple[int, int], int] = {(0, 0): 10}
        for dx, dy in GRID_OUTWARD_DELTA.values():
            z[(dx, dy)] = 0
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((0, 0),), (), z_height_map=z)
        err.assert_called_once()
        self.assertEqual(err.call_args.kwargs["slots"], "... .#. ...")
        self.assertEqual(err.call_args.kwargs["open"], "NW,N,NE,W,E,SW,S,SE")

    def test_different_z_without_ray_logs_shared_facings(self) -> None:
        z = {(4, 8): 142, (4, 7): 122}
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((4, 8), (4, 7)), (), z_height_map=z)
        self.assertEqual(err.call_count, 2)
        sender_call = next(c for c in err.call_args_list if c.kwargs["y"] == 8)
        recv_call = next(c for c in err.call_args_list if c.kwargs["y"] == 7)
        self.assertEqual(sender_call.args[0], EVENT_GRADE_CELL_EMPTY_RAY)
        self.assertEqual(sender_call.kwargs["slots"], "### ### #.#")
        self.assertEqual(recv_call.kwargs["slots"], "#.# ### ###")
        self.assertEqual(sender_call.kwargs["open"], "S")
        self.assertEqual(recv_call.kwargs["open"], "N")

    def test_pack_slots_close_different_z(self) -> None:
        sender = _sender(x=4, y=8)
        slots = pack_rim_slot_rays(
            (sender,),
            cells={(4, 8), (4, 7)},
        )
        z = {(4, 8): 142, (4, 7): 122}
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((4, 8), (4, 7)), slots, z_height_map=z)
        err.assert_not_called()

    def test_progress_reports_empty_count_once_at_end(self) -> None:
        z: dict[tuple[int, int], int] = {(0, 0): 10}
        for dx, dy in GRID_OUTWARD_DELTA.values():
            z[(dx, dy)] = 0
        ticks: list[tuple[int, int]] = []
        n_empty = validate_grade_cell_empty_rays(
            ((0, 0),),
            (),
            z_height_map=z,
            on_progress=lambda done, empty: ticks.append((done, empty)),
            progress_every=1,
        )
        self.assertEqual(n_empty, 1)
        self.assertEqual(ticks, [(1, 1)])

    def test_leftover_plus_halo_excludes_far_plains(self) -> None:
        rays = (
            GradeRimRay(x=0, y=0, facing=Facing.EAST, kind=ReliefSideKind.SLOPE),
        )
        z = {(0, 0): 8, (1, 0): 6, (50, 50): 4, (51, 50): 3}
        uni = set(leftover_plus_halo(rays, z))
        self.assertIn((0, 0), uni)
        self.assertIn((1, 0), uni)
        self.assertNotIn((50, 50), uni)
        self.assertNotIn((51, 50), uni)

    def test_one_leftover_does_not_close_interior_cell(self) -> None:
        """Neighbor in ``z_height_map`` without a pack slot is empty — omit cannot hide it.

        Does not run persist downhill-fill: that would close the other seven
        facings. This is the validator itself.
        """
        z: dict[tuple[int, int], int] = {(0, 0): 10}
        for dx, dy in GRID_OUTWARD_DELTA.values():
            z[(dx, dy)] = 0
        leftover = pack_rim_slot_rays(
            (
                GradeRimRay(x=0, y=0, facing=Facing.SOUTH, kind=ReliefSideKind.SHEER),
            ),
            cells=set(z),
        )
        halo = leftover_plus_halo(leftover, z)
        slots = merge_grade_rim_rays(
            leftover,
            couple_rim_rays(halo, leftover, z),
        )
        self.assertTrue(_has_eight_neighbors((0, 0), z))
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            n_empty = validate_grade_cell_empty_rays(
                halo, slots, z_height_map=z,
            )
        self.assertGreaterEqual(n_empty, 1)
        center = next(
            c for c in err.call_args_list
            if c.kwargs["x"] == 0 and c.kwargs["y"] == 0
        )
        self.assertIn("E", center.kwargs["open"].split(","))
        self.assertNotEqual(center.kwargs["open"], "")

    def test_downhill_fill_closes_interior_drop(self) -> None:
        """Persist fill writes the other downhill facings; validator empty=0."""
        z: dict[tuple[int, int], int] = {(0, 0): 10}
        for dx, dy in GRID_OUTWARD_DELTA.values():
            z[(dx, dy)] = 0
        leftover = pack_rim_slot_rays(
            (
                GradeRimRay(x=0, y=0, facing=Facing.SOUTH, kind=ReliefSideKind.SHEER),
            ),
            cells=set(z),
        )
        extra = downhill_leftover_rim_rays(leftover, z)
        self.assertTrue(any(r.facing is Facing.EAST for r in extra if r.cell == (0, 0)))
        slots, halo = pack_slots_for_persist(leftover, z)
        present = {ray.facing for ray in slots if ray.cell == (0, 0)}
        self.assertEqual(present, set(Facing))
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            n_empty = validate_grade_cell_empty_rays(
                halo, slots, z_height_map=z,
            )
        err.assert_not_called()
        self.assertEqual(n_empty, 0)


class TestDiscoverPackClosesR44(unittest.TestCase):
    """Discover leftover + persist COUPLE must satisfy the R44 validator.

    Maps keep every tested cell interior (all 8 neighbors in ``z_height_map``)
    so omit cannot treat an empty Facing as closed.
    """

    def _assert_validator_clean(
        self,
        slots: tuple[GradeRimRay, ...],
        halo: tuple[tuple[int, int], ...],
        z: dict[tuple[int, int], int],
        *interior: tuple[int, int],
    ) -> None:
        for cell in interior:
            self.assertTrue(_has_eight_neighbors(cell, z), cell)
            present = {ray.facing for ray in slots if ray.cell == cell}
            self.assertEqual(present, set(Facing), cell)
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            n_empty = validate_grade_cell_empty_rays(
                halo, slots, z_height_map=z,
            )
        err.assert_not_called()
        self.assertEqual(n_empty, 0)

    def test_isolated_unit_ledge_closes_all_interior_slots(self) -> None:
        """``4|3`` terrace, not a 1×1 hole: uid corridor on the first 3; R44 empty=0."""
        z = _rect_z(6, 3, lambda x, _y: 4 if x <= 2 else 3)
        fronts = _discover_open_land(z)
        east = [f for f in fronts if f.outward is Facing.EAST]
        self.assertTrue(east)
        lower = {(x, y) for x, y in z if z[(x, y)] == 3}
        corridor = {xy for f in east for xy in f.corridor}
        self.assertTrue(corridor & lower)
        self.assertTrue(corridor)
        slots, halo = _pack_like_persist(_leftover_from_fronts(fronts), z)
        self.assertTrue(halo)
        self._assert_validator_clean(slots, halo, z, (2, 1), (3, 1))

    def test_isolated_peak_closes_center_eight_slots(self) -> None:
        z = _rect_z(3, 3, lambda x, y: 4 if (x, y) == (1, 1) else 2)
        fronts = _discover_open_land(z)
        self.assertEqual({f.outward for f in fronts}, set(Facing))
        slots, halo = _pack_like_persist(_leftover_from_fronts(fronts), z)
        self._assert_validator_clean(slots, halo, z, (1, 1))

    def test_one_by_one_hole_is_not_leftover_plus_halo(self) -> None:
        """C41 skip: no leftover, so the validator does not demand eight slots on the ring."""
        z = _rect_z(3, 3, lambda x, y: 2 if (x, y) == (1, 1) else 4)
        fronts = _discover_open_land(z)
        self.assertEqual(fronts, ())
        leftover = _leftover_from_fronts(fronts)
        self.assertEqual(leftover, ())
        slots, halo = _pack_like_persist(leftover, z)
        self.assertEqual(halo, ())
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            n_empty = validate_grade_cell_empty_rays(
                halo, slots, z_height_map=z,
            )
        err.assert_not_called()
        self.assertEqual(n_empty, 0)


if __name__ == "__main__":
    unittest.main()
