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
from app.dataModel.spatial.facing import Facing, opposite
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

    def test_walk_width_equal_z_one_owner(self) -> None:
        keys = set(walk_pack_senders(((0, 10), (1, 10)), (), Facing.SOUTH))
        self.assertIn(((0, 10), Facing.EAST), keys)
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

    def test_body_equal_z_one_owner(self) -> None:
        body = {(0, 0): 5, (1, 0): 5}
        z = {**body}
        keys = set(body_pack_senders(body, z.get))
        self.assertIn(((0, 0), Facing.EAST), keys)
        self.assertNotIn(((1, 0), Facing.WEST), keys)

    def test_vertex_bodies_use_painted_kind_then_model_default(self) -> None:
        verts = ReliefVertices.for_bounds(origin_x=0, origin_y=920, width=3, height=8)
        verts.add_vertex({(1, 924): 142})
        z = {(1, 924): 142, (1, 923): 122, (2, 924): 142}
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
            validate_grade_cell_empty_rays((cell,), rays)
        err.assert_not_called()

    def test_empty_side_logs_error_and_does_not_raise(self) -> None:
        sender = _sender(x=4, y=8)
        slots = pack_rim_slot_rays(
            (sender,),
            cells={(4, 8), (4, 7)},
        )
        with patch(
            "app.application.worldData.generators.terrain.relief.validate.gradeCellRays.relief_error",
        ) as err:
            validate_grade_cell_empty_rays(((4, 8), (4, 7)), slots)
        self.assertEqual(err.call_count, 2)
        sender_call = next(c for c in err.call_args_list if c.kwargs["y"] == 8)
        recv_call = next(c for c in err.call_args_list if c.kwargs["y"] == 7)
        self.assertEqual(sender_call.args[0], EVENT_GRADE_CELL_EMPTY_RAY)
        self.assertNotIn("south", sender_call.kwargs["empty_facings"])
        self.assertIn("north", sender_call.kwargs["empty_facings"])
        self.assertNotIn("north", recv_call.kwargs["empty_facings"])
        self.assertIn("south", recv_call.kwargs["empty_facings"])


if __name__ == "__main__":
    unittest.main()
