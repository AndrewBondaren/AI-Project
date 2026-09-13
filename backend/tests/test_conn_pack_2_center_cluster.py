"""CONN-PACK-2 — center cluster around district home module."""

from __future__ import annotations

import random
import unittest

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.cluster import (
    cluster_id_for,
    frame_blocked_rects,
    reservation_modules,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.frontage import (
    add_alleys,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.lattice import (
    make_lattice,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.occupy import (
    center_module,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.pass1 import (
    run_pass1,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.pass2 import (
    holes_after_frame,
    run_pass2,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    AreaPlacement,
    InnerBBox,
    PackingToken,
    Reservation,
    StreetFrameContext,
)
from app.application.worldData.generators.road.connectionPolicy import paint_for_connection
from app.application.worldData.generators.road.layouts.gridLayout import generate_grid
from app.dataModel.settlement.district.districtConnection import (
    DistrictConnection,
    street_classes_for,
)
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.requiredStructure import POSITION_CENTER
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.settlement.enums.districtStreetRole import DistrictStreetRole
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.dataModel.structure.enums.buildingPurpose import BuildingPurpose


_STEP = 80
_CLUSTER_ID = cluster_id_for("civic_center")


def _inner(modules: int) -> InnerBBox:
    side = modules * _STEP
    return InnerBBox(0, 0, side, side)


def _slot(*connections: DistrictConnection) -> DistrictSlot:
    template = DistrictTemplateEntry(
        system_name="civic_center",
        display_name="x",
        district_type="civic",
        density=DistrictDensity.DENSE,
        connections=list(connections) or None,
    )
    inner = _inner(3)
    return DistrictSlot(
        origin_x=inner.x0,
        origin_y=inner.y0,
        width_fine=inner.width,
        depth_fine=inner.height,
        ground_z=0,
        district_template=template,
    )


def _token(
    uid: str,
    *,
    w: int = 10,
    h: int = 10,
    required: bool = True,
    position: str | None = POSITION_CENTER,
    priority: int = 0,
    copy_index: int = 0,
    system_name: str | None = None,
) -> PackingToken:
    name = system_name or uid.split("#", 1)[0]
    return PackingToken(
        uid=uid,
        system_name=name,
        w=w,
        h=h,
        priority=priority,
        required=required,
        position=position,
        copy_index=copy_index,
        n_from="required",
    )


def _min_manhattan(reservation: Reservation, home: tuple[int, int]) -> int:
    home_c, home_r = home
    return min(
        abs(col - home_c) + abs(row - home_r)
        for col, row in reservation_modules(reservation)
    )


def _four_adjacent(left: Reservation, right: Reservation) -> bool:
    a = reservation_modules(left)
    b = reservation_modules(right)
    for col, row in a:
        if (col + 1, row) in b or (col - 1, row) in b:
            return True
        if (col, row + 1) in b or (col, row - 1) in b:
            return True
    return False


def _skeleton() -> CitySkeleton:
    return CitySkeleton(
        economic_tier=None,
        architectural_style=None,
        dominant_material=None,
        settlement_density=DistrictDensity.DENSE,
        system_city_size=None,
        system_location_mood=None,
    )


def _layout(system_name: str, purpose: str = "town_hall") -> BuildingLayoutTemplate:
    return BuildingLayoutTemplate(
        system_name=system_name,
        structure_type=purpose,
        display_name=system_name,
        occupied_footprint={"width": 4, "depth": 4},
    )


def _placement(
    token: PackingToken,
    *,
    col: int,
    row: int,
    x: int,
    y: int,
    cluster: bool,
    purpose: str = "town_hall",
) -> AreaPlacement:
    reservation = Reservation(
        token=token,
        col=col,
        row=row,
        span_cols=1,
        span_rows=1,
        rect_xy=(x, y, x + _STEP, y + _STEP),
        rotated_90=False,
        pass_id=1,
        cluster_id=_CLUSTER_ID if cluster else None,
    )
    return AreaPlacement(
        area_slot=AreaSlot(cells=[(x, y)], ground_z=0, facing=Facing.SOUTH),
        template=_layout(token.system_name, purpose),
        building_x=x,
        building_y=y,
        reservation=reservation,
    )


class CenterClusterPass1Test(unittest.TestCase):
    def test_two_centers_fit_adjacent_first_closer_to_home(self) -> None:
        inner = _inner(3)
        lattice = make_lattice(inner, _STEP)
        home = center_module(inner, lattice)
        assert home is not None
        tokens = [
            _token("town_hall#0", copy_index=0),
            _token("cathedral#0", system_name="cathedral"),
        ]
        placed, leftover, occupied = run_pass1(_slot(), inner, lattice, tokens, ())
        self.assertEqual(leftover, [])
        self.assertEqual(len(placed), 2)
        first, second = placed
        self.assertEqual(first.token.uid, "town_hall#0")
        self.assertEqual(first.cluster_id, _CLUSTER_ID)
        self.assertEqual(second.cluster_id, _CLUSTER_ID)
        self.assertIn(home, reservation_modules(first))
        self.assertLessEqual(_min_manhattan(first, home), _min_manhattan(second, home))
        self.assertTrue(_four_adjacent(first, second))
        hull = frame_blocked_rects(placed)
        self.assertEqual(len(hull), 1)
        self.assertEqual(hull[0][0], min(first.rect_xy[0], second.rect_xy[0]))
        self.assertEqual(hull[0][2], max(first.rect_xy[2], second.rect_xy[2]))

    def test_second_center_leftover_when_no_neighbor(self) -> None:
        inner = _inner(1)
        lattice = make_lattice(inner, _STEP)
        home = center_module(inner, lattice)
        assert home is not None
        tokens = [
            _token("town_hall#0"),
            _token("cathedral#0", system_name="cathedral"),
        ]
        slot = DistrictSlot(
            origin_x=0, origin_y=0, width_fine=_STEP, depth_fine=_STEP, ground_z=0,
            district_template=_slot().district_template,
        )
        placed, leftover, occupied = run_pass1(slot, inner, lattice, tokens, ())
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0].token.uid, "town_hall#0")
        self.assertIn(home, reservation_modules(placed[0]))
        self.assertEqual([token.uid for token in leftover], ["cathedral#0"])
        holes = holes_after_frame(lattice, occupied)
        pass2, leftover2 = run_pass2(slot, tokens, holes)
        self.assertEqual(pass2, [])
        self.assertNotIn("cathedral#0", {row.token.uid for row in pass2})
        self.assertTrue(all(cell for row in occupied for cell in row))

    def test_failed_first_leaves_home_for_second(self) -> None:
        inner = _inner(3)
        lattice = make_lattice(inner, _STEP)
        home = center_module(inner, lattice)
        assert home is not None
        tokens = [
            _token("huge#0", w=1000, h=1000, system_name="huge"),
            _token("town_hall#0"),
        ]
        placed, leftover, _occupied = run_pass1(_slot(), inner, lattice, tokens, ())
        self.assertEqual([token.uid for token in leftover], ["huge#0"])
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0].token.uid, "town_hall#0")
        self.assertIn(home, reservation_modules(placed[0]))

    def test_canonical_civic_one_town_hall_on_home(self) -> None:
        civic = WorldDistrictTemplateRegistry.canonical_defaults().entry_for(
            "civic_center",
        )
        assert civic is not None
        self.assertEqual(len(civic.required_structures or []), 1)
        self.assertEqual(civic.required_structures[0].plot_template, "town_hall")
        self.assertEqual(civic.required_structures[0].position, POSITION_CENTER)
        inner = _inner(3)
        lattice = make_lattice(inner, _STEP)
        home = center_module(inner, lattice)
        assert home is not None
        placed, leftover, _occupied = run_pass1(
            _slot(), inner, lattice, [_token("town_hall#0")], (),
        )
        self.assertEqual(leftover, [])
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0].cluster_id, _CLUSTER_ID)
        self.assertIn(home, reservation_modules(placed[0]))
        self.assertEqual(frame_blocked_rects(placed), (placed[0].rect_xy,))

    def test_count_two_same_drawing_in_cluster(self) -> None:
        inner = _inner(3)
        lattice = make_lattice(inner, _STEP)
        tokens = [
            _token("town_hall#0", copy_index=0),
            _token("town_hall#1", copy_index=1),
        ]
        placed, leftover, _occupied = run_pass1(_slot(), inner, lattice, tokens, ())
        self.assertEqual(leftover, [])
        self.assertEqual([row.token.uid for row in placed], ["town_hall#0", "town_hall#1"])
        self.assertTrue(all(row.cluster_id == _CLUSTER_ID for row in placed))
        self.assertTrue(_four_adjacent(placed[0], placed[1]))

    def test_plot_priority_without_center_is_not_cluster(self) -> None:
        inner = _inner(3)
        lattice = make_lattice(inner, _STEP)
        home = center_module(inner, lattice)
        assert home is not None
        tokens = [
            _token("town_hall#0"),
            _token(
                "manor#0",
                required=False,
                position=None,
                priority=10,
                system_name="manor",
            ),
        ]
        placed, leftover, _occupied = run_pass1(_slot(), inner, lattice, tokens, ())
        self.assertEqual(leftover, [])
        by_uid = {row.token.uid: row for row in placed}
        self.assertEqual(by_uid["town_hall#0"].cluster_id, _CLUSTER_ID)
        self.assertIsNone(by_uid["manor#0"].cluster_id)
        self.assertNotIn(home, reservation_modules(by_uid["manor#0"]))
        blocked = frame_blocked_rects(placed)
        self.assertEqual(len(blocked), 2)
        self.assertEqual(blocked[0], by_uid["town_hall#0"].rect_xy)
        self.assertEqual(blocked[1], by_uid["manor#0"].rect_xy)

    def test_plaza_pin_joins_cluster_packing_does_not_invent(self) -> None:
        inner = _inner(3)
        lattice = make_lattice(inner, _STEP)
        with_plaza = [
            _token("town_hall#0"),
            _token("plaza_1#0", system_name="plaza_1"),
        ]
        placed, leftover, _occupied = run_pass1(_slot(), inner, lattice, with_plaza, ())
        self.assertEqual(leftover, [])
        self.assertEqual({row.token.system_name for row in placed}, {"town_hall", "plaza_1"})
        self.assertTrue(all(row.cluster_id == _CLUSTER_ID for row in placed))
        halls_only = [_token("town_hall#0"), _token("cathedral#0", system_name="cathedral")]
        placed_halls, leftover_halls, _occ = run_pass1(
            _slot(), inner, lattice, halls_only, (),
        )
        self.assertEqual(leftover_halls, [])
        self.assertNotIn("plaza_1", {row.token.system_name for row in placed_halls})
        plaza = _layout("plaza_1", BuildingPurpose.PLAZA.value)
        self.assertIn(BuildingPurpose.PLAZA, plaza.structure_types)


class CenterClusterFrameAlleyTest(unittest.TestCase):
    def test_frame_omits_street_on_cluster_shared_edge(self) -> None:
        inner = _inner(3)
        lattice = make_lattice(inner, _STEP)
        tokens = [
            _token("town_hall#0"),
            _token("cathedral#0", system_name="cathedral"),
        ]
        slot = _slot(
            DistrictConnection(connection_type="road", role="main_street"),
        )
        placed, leftover, _occupied = run_pass1(slot, inner, lattice, tokens, ())
        self.assertEqual(leftover, [])
        hull = frame_blocked_rects(placed)
        self.assertEqual(len(hull), 1)
        classes = street_classes_for(slot.district_template)
        _nodes, edges, _roles = generate_grid(
            slot, _skeleton(), "w",
            paint_for_connection(classes.fill),
            paint_for_connection(classes.spine),
            random.Random(0),
            frame=StreetFrameContext(
                inner=inner, step=_STEP, blocked_rects=hull, corridor_rects=(),
            ),
        )
        first, second = placed
        if first.row == second.row:
            shared_x = max(first.rect_xy[0], second.rect_xy[0])
            y0 = first.rect_xy[1]
            y1 = first.rect_xy[3]
            interior = (shared_x, y0, shared_x, y1)
        else:
            shared_y = max(first.rect_xy[1], second.rect_xy[1])
            x0 = first.rect_xy[0]
            x1 = first.rect_xy[2]
            interior = (x0, shared_y, x1, shared_y)
        node_by_uid = {node.node_uid: node for node in _nodes}
        for edge in edges:
            a = node_by_uid[edge.from_node_uid]
            b = node_by_uid[edge.to_node_uid]
            pair = {(a.x, a.y), (b.x, b.y)}
            if interior[0] == interior[2]:
                self.assertNotEqual(
                    pair,
                    {(interior[0], interior[1]), (interior[2], interior[3])},
                )
            else:
                self.assertNotEqual(
                    pair,
                    {(interior[0], interior[1]), (interior[2], interior[3])},
                )

        split = generate_grid(
            slot, _skeleton(), "w",
            paint_for_connection(classes.fill),
            paint_for_connection(classes.spine),
            random.Random(0),
            frame=StreetFrameContext(
                inner=inner,
                step=_STEP,
                blocked_rects=tuple(row.rect_xy for row in placed),
                corridor_rects=(),
            ),
        )
        split_nodes = {node.node_uid: node for node in split[0]}
        split_has_shared = False
        want = {(interior[0], interior[1]), (interior[2], interior[3])}
        for edge in split[1]:
            a = split_nodes[edge.from_node_uid]
            b = split_nodes[edge.to_node_uid]
            if {(a.x, a.y), (b.x, b.y)} == want:
                split_has_shared = True
                break
        self.assertTrue(split_has_shared)

    def test_canon_civic_has_no_alley_edge(self) -> None:
        civic = WorldDistrictTemplateRegistry.canonical_defaults().entry_for(
            "civic_center",
        )
        assert civic is not None
        self.assertIsNone(street_classes_for(civic).alley)
        slot = DistrictSlot(
            origin_x=0, origin_y=0, width_fine=240, depth_fine=240, ground_z=0,
            district_template=civic,
        )
        nodes: list = []
        edges: list = []
        add_alleys(
            slot,
            [
                _placement(_token("town_hall#0"), col=1, row=1, x=80, y=80, cluster=True),
            ],
            nodes,
            edges,
            "w",
        )
        self.assertEqual(edges, [])

    def test_alley_overlay_emits_cluster_edge(self) -> None:
        slot = _slot(
            DistrictConnection(connection_type="road", role="main_street"),
            DistrictConnection(connection_type="alley", role="back_alley"),
        )
        self.assertIsNotNone(street_classes_for(slot.district_template).alley)
        nodes: list = []
        edges: list = []
        roles: dict[str, DistrictStreetRole] = {}
        add_alleys(
            slot,
            [
                _placement(_token("town_hall#0"), col=1, row=1, x=80, y=80, cluster=True),
                _placement(
                    _token("cathedral#0", system_name="cathedral"),
                    col=2, row=1, x=160, y=80, cluster=True,
                ),
            ],
            nodes,
            edges,
            "w",
            edge_roles=roles,
        )
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].connection_type, "alley")
        self.assertEqual(roles[edges[0].edge_uid], DistrictStreetRole.BACK_ALLEY)


if __name__ == "__main__":
    unittest.main()
