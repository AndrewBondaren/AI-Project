"""Pack rim edge: sender C41 + receiver opposite — tz_terrain_relief_consume."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.application.worldData.generators.terrain.relief.discover.packSenders import (
    body_pack_senders,
    walk_pack_senders,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    DiscoveredFront,
    GradePaintSpec,
    ReliefVertices,
)
from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_GRADE_CELL_EMPTY_RAY,
)
from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    RibbonGradeDecision,
)
from app.application.worldData.generators.terrain.relief.validate.gradeCellRays import (
    validate_grade_cell_empty_rays,
)
from app.application.worldData.pack.refine.gradeRimRays import (
    pack_rays_from_vertex_bodies,
    rim_rays_from_front,
)
from app.dataModel.spatial.facing import Facing, GRID_OUTWARD_DELTA, opposite
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefSideKind
from app.dataModel.terrain.relief.gradeRimRay import (
    GradeRimRay,
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


class TestWalkAndBodyPackSenders(unittest.TestCase):
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

    def test_body_downhill_south_toward_923(self) -> None:
        z = {(10, 924): 142, (10, 923): 122}
        keys = body_pack_senders({(10, 924): 142}, z.get)
        self.assertIn(((10, 924), Facing.SOUTH), keys)
        self.assertNotIn(((10, 924), Facing.NORTH), keys)

    def test_body_equal_z_is_not_pack_sender(self) -> None:
        body = {(0, 0): 5, (1, 0): 5}
        z = {**body}
        keys = set(body_pack_senders(body, z.get))
        self.assertEqual(keys, set())

    def test_vertex_bodies_use_painted_kind_then_model_default(self) -> None:
        verts = ReliefVertices.for_bounds(origin_x=0, origin_y=920, width=3, height=8)
        verts.add_vertex({(1, 924): 142})
        z = {(1, 924): 142, (1, 923): 122, (2, 924): 141}
        rays = pack_rays_from_vertex_bodies(
            verts,
            z.get,
            {(1, Facing.SOUTH): ReliefSideKind.SHEER},
        )
        by = {(r.x, r.y, r.facing): r for r in rays}
        self.assertEqual(by[(1, 924, Facing.SOUTH)].kind, ReliefSideKind.SHEER)
        omitted = GradeRimRay(x=0, y=0, facing=Facing.EAST)
        self.assertEqual(omitted.kind, ReliefSideKind.SLOPE)
        self.assertEqual(by[(1, 924, Facing.EAST)].kind, omitted.kind)


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
            validate_grade_cell_empty_rays((cell,), rays, z_at={(0, 0): 1})
        err.assert_not_called()

    def test_isolated_cell_omits_missing_neighbors(self) -> None:
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((0, 0),), (), z_at={(0, 0): 1})
        err.assert_not_called()

    def test_same_z_neighbors_couple_without_pack_ray(self) -> None:
        z = {(0, 0): 5, (1, 0): 5}
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((0, 0), (1, 0)), (), z_at=z)
        err.assert_not_called()

    def test_all_eight_open_when_neighbors_different_z(self) -> None:
        z: dict[tuple[int, int], int] = {(0, 0): 10}
        for dx, dy in GRID_OUTWARD_DELTA.values():
            z[(dx, dy)] = 0
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((0, 0),), (), z_at=z)
        err.assert_called_once()
        self.assertEqual(err.call_args.kwargs["slots"], "... .#. ...")
        self.assertEqual(err.call_args.kwargs["open"], "NW,N,NE,W,E,SW,S,SE")

    def test_different_z_without_ray_logs_shared_facings(self) -> None:
        z = {(4, 8): 142, (4, 7): 122}
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((4, 8), (4, 7)), (), z_at=z)
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
            validate_grade_cell_empty_rays(((4, 8), (4, 7)), slots, z_at=z)
        err.assert_not_called()

    def test_progress_reports_empty_count_once_at_end(self) -> None:
        z: dict[tuple[int, int], int] = {(0, 0): 10}
        for dx, dy in GRID_OUTWARD_DELTA.values():
            z[(dx, dy)] = 0
        ticks: list[tuple[int, int]] = []
        n_empty = validate_grade_cell_empty_rays(
            ((0, 0),),
            (),
            z_at=z,
            on_progress=lambda done, empty: ticks.append((done, empty)),
            progress_every=1,
        )
        self.assertEqual(n_empty, 1)
        self.assertEqual(ticks, [(1, 1)])


if __name__ == "__main__":
    unittest.main()
