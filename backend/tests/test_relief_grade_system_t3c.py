"""T-3c: ReliefGradeSystem from same-vertex fronts (slot + C29 body UF)."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.volume.gradeInstanceFactory import (
    make_grade_system_uid,
)
from app.application.worldData.gradeInstanceMerge import merge_grade_instances
from app.application.worldData.gradeVertexSystem import emit_relief_grade_systems
from app.application.worldData.pack.refine.detailedGradeCatalog import (
    TileFaceCatalog,
    build_tile_face_catalog,
)
from app.application.worldData.pack.refine.detailedGradeDiscover import discover_and_paint
from app.application.worldData.pack.refine.fineTileContext import VertexSlotSeam
from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain, ReliefContext, ReliefSideKind
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefSlopeGeom import angle_from_height_length
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.db.models.world import World

_MASKS = WorldTerrainMasks.canonical_defaults()
_PLAINS = _MASKS.default_plains.system_terrain
_ROAD = _MASKS.default_roads.system_terrain


def _sheer(uid: str, cells: list[tuple[int, int]], world: str = "w") -> ReliefGradeInstance:
    return ReliefGradeInstance(
        grade_uid=uid,
        world_uid=world,
        kind=ReliefSideKind.SHEER,
        height_cells=2,
        length_cells=1,
        cell_refs=cells,
        angle_deg=angle_from_height_length(2, 1),
    )


def _catalog(*, tile_w: int, tile_h: int, chunk_size: int) -> TileFaceCatalog:
    return build_tile_face_catalog(
        world_seed="s",
        tile_gx=0,
        tile_gy=0,
        origin_x=0,
        origin_y=0,
        tile_w=tile_w,
        tile_h=tile_h,
        chunk_size=chunk_size,
    )


def _seam(
    slot: int,
    uids: tuple[str, ...],
    edge: tuple[tuple[int, int, int], ...],
) -> VertexSlotSeam:
    return VertexSlotSeam(slot=slot, grade_uids=uids, edge_body=edge)


def _open_template() -> tuple[str, ReliefTemplate]:
    tpl = ReliefTemplate.model_validate({
        "system_name": "open_step",
        "display_name": "Open",
        "context": ReliefContext.OPEN_LAND.value,
        "conditions": [{
            "terrain": ReliefConditionTerrain.PLAINS.value,
            "cases": [
                {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
            ],
        }],
    })
    return relief_template_uid("open_step"), tpl


def _road_template() -> tuple[str, ReliefTemplate]:
    tpl = ReliefTemplate.model_validate({
        "system_name": "shoulder_step",
        "display_name": "Shoulder",
        "context": ReliefContext.ROAD_SHOULDER.value,
        "conditions": [{
            "terrain": ReliefConditionTerrain.PLAINS.value,
            "cases": [
                {"policy": "slope_down", "delta_z": 1, "slope_weight": 0.0, "sheer_weight": 1.0},
                {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
            ],
        }],
    })
    return relief_template_uid("shoulder_step"), tpl


def _world(world_uid: str, tpl_uid: str, context: ReliefContext) -> World:
    return World(
        world_uid=world_uid,
        name="W",
        created_at="2026-01-01T00:00:00Z",
        relief_template_registry=[{
            "system_template_uid": tpl_uid,
            "context": context.value,
            "display_template_name": "T",
        }],
        relief_pick_policy={
            context.value: {"mode": "fixed", "default_template_uid": tpl_uid},
        },
    )


def _state(
    world_uid: str,
    z: dict[tuple[int, int], int],
    terrain: dict[tuple[int, int], str],
) -> TileSurfaceState:
    xs = [x for x, _y in z]
    ys = [y for _x, y in z]
    return TileSurfaceState(
        heightmap=SurfaceHeightmap(
            world_uid=world_uid,
            bbox=GridBBox(x_min=min(xs), x_max=max(xs), y_min=min(ys), y_max=max(ys)),
            surface_z=z,
        ),
        n_eff={xy: 1 for xy in z},
        hydrology=None,
        surface_terrain=terrain,
    )


def _assert_cells_are_instance_uids(
    test: unittest.TestCase,
    surface_grade_uid: dict[tuple[int, int], str],
    instances: tuple[ReliefGradeInstance, ...],
    systems: tuple,
) -> None:
    inst_uids = {inst.grade_uid for inst in instances}
    system_uids = {sys.grade_system_uid for sys in systems}
    test.assertTrue(surface_grade_uid)
    for uid in surface_grade_uid.values():
        test.assertIn(uid, inst_uids)
        test.assertNotIn(uid, system_uids)


class EmitGradeSystemsTest(unittest.TestCase):
    def test_intra_chunk_two_fronts_one_system(self) -> None:
        inst_a = _sheer("ga", [(1, 0)])
        inst_b = _sheer("gb", [(0, 1)])
        catalog = _catalog(tile_w=4, tile_h=4, chunk_size=4)
        rect = ColumnRect(0, 3, 0, 3)
        traces = [(rect, (_seam(1, ("ga", "gb"), ((0, 3, 6),)),))]
        instances, systems = emit_relief_grade_systems(
            (inst_a, inst_b), traces, catalog,
        )
        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0].grade_instance_uids, ["ga", "gb"])
        by_uid = {inst.grade_uid: inst for inst in instances}
        self.assertEqual(by_uid["ga"].grade_system_uid, systems[0].grade_system_uid)
        self.assertEqual(by_uid["gb"].grade_system_uid, systems[0].grade_system_uid)
        expected = make_grade_system_uid(world_uid="w", site_id="ga|gb")
        self.assertEqual(systems[0].grade_system_uid, expected)

    def test_one_front_no_system(self) -> None:
        inst = _sheer("g1", [(1, 0)])
        catalog = _catalog(tile_w=4, tile_h=4, chunk_size=4)
        rect = ColumnRect(0, 3, 0, 3)
        traces = [(rect, (_seam(1, ("g1",), ((3, 1, 6),)),))]
        instances, systems = emit_relief_grade_systems((inst,), traces, catalog)
        self.assertEqual(systems, ())
        self.assertIsNone(instances[0].grade_system_uid)

    def test_two_chunks_body_8_across_vertical_seam(self) -> None:
        south = _sheer("south", [(1, 0)])
        east = _sheer("east", [(6, 2)])
        catalog = _catalog(tile_w=8, tile_h=4, chunk_size=4)
        rect_a = ColumnRect(0, 3, 0, 3)
        rect_b = ColumnRect(4, 7, 0, 3)
        traces = [
            (rect_a, (_seam(1, ("south",), ((3, 2, 6), (3, 3, 6))),)),
            (rect_b, (_seam(1, ("east",), ((4, 2, 6), (4, 3, 6))),)),
        ]
        instances, systems = emit_relief_grade_systems(
            (south, east), traces, catalog,
        )
        self.assertEqual(len(systems), 1)
        self.assertEqual(set(systems[0].grade_instance_uids), {"south", "east"})
        by_uid = {inst.grade_uid: inst for inst in instances}
        self.assertEqual(by_uid["south"].grade_system_uid, systems[0].grade_system_uid)
        self.assertEqual(by_uid["east"].grade_system_uid, systems[0].grade_system_uid)

        reversed_traces = list(reversed(traces))
        again, systems_rev = emit_relief_grade_systems(
            (east, south), reversed_traces, catalog,
        )
        self.assertEqual(systems[0].grade_system_uid, systems_rev[0].grade_system_uid)
        self.assertEqual(
            {inst.grade_system_uid for inst in again},
            {systems[0].grade_system_uid},
        )

    def test_diagonal_8_across_vertical_seam(self) -> None:
        left = _sheer("gl", [(1, 0)])
        right = _sheer("gr", [(6, 2)])
        catalog = _catalog(tile_w=8, tile_h=4, chunk_size=4)
        traces = [
            (ColumnRect(0, 3, 0, 3), (_seam(1, ("gl",), ((3, 2, 6),)),)),
            (ColumnRect(4, 7, 0, 3), (_seam(1, ("gr",), ((4, 3, 6),)),)),
        ]
        _instances, systems = emit_relief_grade_systems(
            (left, right), traces, catalog,
        )
        self.assertEqual(len(systems), 1)
        self.assertEqual(set(systems[0].grade_instance_uids), {"gl", "gr"})

    def test_two_hills_same_z_bodies_do_not_touch(self) -> None:
        a = _sheer("ha", [(1, 0)])
        b = _sheer("hb", [(6, 2)])
        catalog = _catalog(tile_w=8, tile_h=4, chunk_size=4)
        traces = [
            (ColumnRect(0, 3, 0, 3), (_seam(1, ("ha",), ((3, 0, 6),)),)),
            (ColumnRect(4, 7, 0, 3), (_seam(1, ("hb",), ((4, 3, 6),)),)),
        ]
        instances, systems = emit_relief_grade_systems((a, b), traces, catalog)
        self.assertEqual(systems, ())
        self.assertTrue(all(inst.grade_system_uid is None for inst in instances))

    def test_three_chunks_one_mesa_one_system(self) -> None:
        a = _sheer("ma", [(1, 0)])
        b = _sheer("mb", [(6, 1)])
        c = _sheer("mc", [(1, 6)])
        catalog = _catalog(tile_w=8, tile_h=8, chunk_size=4)
        traces = [
            (
                ColumnRect(0, 3, 0, 3),
                (_seam(1, ("ma",), ((3, 2, 6), (2, 3, 6))),),
            ),
            (ColumnRect(4, 7, 0, 3), (_seam(1, ("mb",), ((4, 2, 6),)),)),
            (ColumnRect(0, 3, 4, 7), (_seam(1, ("mc",), ((2, 4, 6),)),)),
        ]
        instances, systems = emit_relief_grade_systems((a, b, c), traces, catalog)
        self.assertEqual(len(systems), 1)
        self.assertEqual(set(systems[0].grade_instance_uids), {"ma", "mb", "mc"})
        sys_uid = systems[0].grade_system_uid
        self.assertTrue(all(inst.grade_system_uid == sys_uid for inst in instances))

    def test_catalog_merge_one_uid_is_not_a_system(self) -> None:
        shared = _sheer("g-shared", [(2, 1), (5, 1)])
        catalog = _catalog(tile_w=8, tile_h=4, chunk_size=4)
        traces = [
            (ColumnRect(0, 3, 0, 3), (_seam(1, ("g-shared",), ((3, 1, 6),)),)),
            (ColumnRect(4, 7, 0, 3), (_seam(1, ("g-shared",), ((4, 1, 6),)),)),
        ]
        merged = merge_grade_instances([shared, _sheer("g-shared", [(5, 1)])])
        instances, systems = emit_relief_grade_systems(merged, traces, catalog)
        self.assertEqual(len(merged), 1)
        self.assertEqual(systems, ())
        self.assertIsNone(instances[0].grade_system_uid)



    def test_side_attach_one_front_parent_makes_system(self) -> None:
        parent = _sheer("gp", [(1, 0)])
        child = _sheer("gc", [(2, 0)])
        catalog = _catalog(tile_w=4, tile_h=4, chunk_size=4)
        rect = ColumnRect(0, 3, 0, 3)
        traces = [(rect, (
            _seam(1, ("gp",), ((0, 3, 6),)),
            VertexSlotSeam(
                slot=2, grade_uids=("gc",), edge_body=((0, 0, 3),),
                side_parent_slot=1,
            ),
        ))]
        instances, systems = emit_relief_grade_systems(
            (parent, child), traces, catalog,
        )
        self.assertEqual(len(systems), 1)
        self.assertEqual(set(systems[0].grade_instance_uids), {"gp", "gc"})
        by_uid = {inst.grade_uid: inst for inst in instances}
        self.assertEqual(by_uid["gp"].grade_system_uid, systems[0].grade_system_uid)
        self.assertEqual(by_uid["gc"].grade_system_uid, systems[0].grade_system_uid)

    def test_side_without_parent_trace_has_no_system(self) -> None:
        child = _sheer("gc", [(2, 0)])
        catalog = _catalog(tile_w=4, tile_h=4, chunk_size=4)
        rect = ColumnRect(0, 3, 0, 3)
        traces = [(rect, (_seam(2, ("gc",), ((0, 0, 3),)),))]
        instances, systems = emit_relief_grade_systems((child,), traces, catalog)
        self.assertEqual(systems, ())
        self.assertIsNone(instances[0].grade_system_uid)

    def test_side_joins_t3c_system_transitively(self) -> None:
        south = _sheer("south", [(1, 0)])
        east = _sheer("east", [(6, 2)])
        side = _sheer("side", [(0, 1)])
        catalog = _catalog(tile_w=8, tile_h=4, chunk_size=4)
        rect_a = ColumnRect(0, 3, 0, 3)
        rect_b = ColumnRect(4, 7, 0, 3)
        traces = [
            (rect_a, (
                _seam(1, ("south",), ((3, 2, 6), (3, 3, 6))),
                VertexSlotSeam(
                    slot=2, grade_uids=("side",), edge_body=((0, 0, 3),),
                    side_parent_slot=1,
                ),
            )),
            (rect_b, (_seam(1, ("east",), ((4, 2, 6), (4, 3, 6))),)),
        ]
        instances, systems = emit_relief_grade_systems(
            (south, east, side), traces, catalog,
        )
        self.assertEqual(len(systems), 1)
        self.assertEqual(set(systems[0].grade_instance_uids), {"south", "east", "side"})
        uid = systems[0].grade_system_uid
        self.assertTrue(all(inst.grade_system_uid == uid for inst in instances))

    def test_side_chain_unions_in_one_pass(self) -> None:
        a = _sheer("ga", [(1, 0)])
        b = _sheer("gb", [(2, 0)])
        c = _sheer("gc", [(3, 0)])
        catalog = _catalog(tile_w=4, tile_h=4, chunk_size=4)
        rect = ColumnRect(0, 3, 0, 3)
        traces = [(rect, (
            _seam(1, ("ga",), ((0, 3, 6),)),
            VertexSlotSeam(
                slot=2, grade_uids=("gb",), edge_body=((0, 1, 4),),
                side_parent_slot=1,
            ),
            VertexSlotSeam(
                slot=3, grade_uids=("gc",), edge_body=((0, 0, 3),),
                side_parent_slot=2,
            ),
        ))]
        _instances, systems = emit_relief_grade_systems(
            (a, b, c), traces, catalog,
        )
        self.assertEqual(len(systems), 1)
        self.assertEqual(set(systems[0].grade_instance_uids), {"ga", "gb", "gc"})


class DiscoverPaintT3cTest(unittest.TestCase):
    def test_mesa_two_fronts_one_rect_system_and_cell_uid(self) -> None:
        tuid, tpl = _open_template()
        world = _world("w_mesa", tuid, ReliefContext.OPEN_LAND)
        z: dict[tuple[int, int], int] = {}
        terrain: dict[tuple[int, int], str] = {}
        for x in range(4):
            for y in range(4):
                high = x == 0 or y == 0
                z[(x, y)] = 10 if high else 6
                terrain[(x, y)] = _PLAINS
        rect = ColumnRect(0, 3, 0, 3)
        catalog = _catalog(tile_w=4, tile_h=4, chunk_size=4)
        write, seams, _pipeline = discover_and_paint(
            world, _state(world.world_uid, z, terrain), rect,
            halo=2, catalog=catalog, templates={tuid: tpl},
        )
        self.assertGreaterEqual(len({i.grade_uid for i in write.grade_instances}), 2)
        self.assertTrue(seams)
        instances, systems = emit_relief_grade_systems(
            write.grade_instances, [(rect, seams)], catalog,
        )
        self.assertEqual(len(systems), 1)
        member_uids = set(systems[0].grade_instance_uids)
        self.assertGreaterEqual(len(member_uids), 2)
        by_uid = {inst.grade_uid: inst for inst in instances}
        for uid in member_uids:
            self.assertEqual(by_uid[uid].grade_system_uid, systems[0].grade_system_uid)
        _assert_cells_are_instance_uids(
            self, write.surface_grade_uid, instances, systems,
        )

    def test_one_sided_cliff_no_system(self) -> None:
        tuid, tpl = _open_template()
        world = _world("w_cliff", tuid, ReliefContext.OPEN_LAND)
        z = {
            (0, 2): 6, (1, 2): 6,
            (0, 1): 6, (1, 1): 6,
            (0, 0): 2, (1, 0): 2,
        }
        terrain = {xy: _PLAINS for xy in z}
        rect = ColumnRect(0, 1, 0, 2)
        catalog = _catalog(tile_w=2, tile_h=3, chunk_size=4)
        write, seams, _pipeline = discover_and_paint(
            world, _state(world.world_uid, z, terrain), rect,
            halo=2, catalog=catalog, templates={tuid: tpl},
        )
        self.assertTrue(write.grade_instances)
        instances, systems = emit_relief_grade_systems(
            write.grade_instances, [(rect, seams)], catalog,
        )
        self.assertEqual(systems, ())
        self.assertTrue(all(inst.grade_system_uid is None for inst in instances))
        _assert_cells_are_instance_uids(
            self, write.surface_grade_uid, instances, systems,
        )

    def test_road_two_ortho_fronts_one_system(self) -> None:
        tuid, tpl = _road_template()
        world = _world("w_road", tuid, ReliefContext.ROAD_SHOULDER)
        z = {
            (0, 2): 2, (1, 2): 2, (2, 2): 2,
            (0, 1): 4, (1, 1): 4, (2, 1): 4,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        terrain = {(x, y): (_ROAD if y == 1 else _PLAINS) for x, y in z}
        rect = ColumnRect(0, 2, 0, 2)
        catalog = _catalog(tile_w=3, tile_h=3, chunk_size=4)
        write, seams, _pipeline = discover_and_paint(
            world, _state(world.world_uid, z, terrain), rect,
            halo=2, catalog=catalog, templates={tuid: tpl},
        )
        self.assertGreaterEqual(len({i.grade_uid for i in write.grade_instances}), 2)
        instances, systems = emit_relief_grade_systems(
            write.grade_instances, [(rect, seams)], catalog,
        )
        self.assertEqual(len(systems), 1)
        self.assertGreaterEqual(len(systems[0].grade_instance_uids), 2)
        _assert_cells_are_instance_uids(
            self, write.surface_grade_uid, instances, systems,
        )


if __name__ == "__main__":
    unittest.main()
