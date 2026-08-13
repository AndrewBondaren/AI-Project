"""Tests for R36u detailed grade generate on meter grid."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.application.worldData.pack.refine.detailedGradeGenerate import generate_detailed_grade
from app.application.worldData.pack.refine.detailedGradeSample import (
    sample_open_land_meter,
    sample_shore_meter,
)
from app.application.worldData.pack.refine.meterGradeSurface import MeterGradeSurface
from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


class DetailedGradeSampleTest(unittest.TestCase):
    def test_open_land_meter_downhill_seed(self) -> None:
        surface = MeterGradeSurface(
            surface_z={(1, 0): 5, (2, 0): 3},
            surface_terrain={(1, 0): "plains", (2, 0): "plains"},
            hydrology=None,
            surface_facing=None,
        )
        samples, refs = sample_open_land_meter(surface, road_key="road")
        self.assertEqual(samples, [((2, 0), "plains", 2)])
        self.assertEqual(refs, {(1, 0)})

    def test_open_land_skips_graded_and_road(self) -> None:
        surface = MeterGradeSurface(
            surface_z={(1, 0): 5, (2, 0): 3, (3, 0): 4, (4, 0): 2},
            surface_terrain={
                (1, 0): "plains", (2, 0): "plains",
                (3, 0): "road", (4, 0): "plains",
            },
            hydrology=None,
            surface_facing=None,
            grade_uid={(2, 0): "g1"},
        )
        samples, _ = sample_open_land_meter(surface, road_key="road")
        seeds = {xy for xy, _, _ in samples}
        self.assertNotIn((2, 0), seeds)
        self.assertNotIn((4, 0), seeds)

    def test_shore_landward_of_shore_role(self) -> None:
        surface = MeterGradeSurface(
            surface_z={(1, 0): 2, (2, 0): 4, (0, 0): 0},
            surface_terrain={
                (1, 0): "shore", (2, 0): "plains", (0, 0): "liquid_body",
            },
            hydrology={
                (1, 0): MapCellHydrology(role=HydrologyCellRole.SHORE),
                (0, 0): MapCellHydrology(role=HydrologyCellRole.LAKE),
            },
            surface_facing=None,
        )
        samples, refs = sample_shore_meter(surface, road_key="road")
        seeds = {xy for xy, _, _ in samples}
        self.assertIn((2, 0), seeds)
        self.assertIn((1, 0), refs)
        self.assertNotIn((0, 0), seeds)

    def test_open_land_rect_owns_seed_only(self) -> None:
        from app.application.worldData.generators.terrain.types import ColumnRect

        surface = MeterGradeSurface(
            surface_z={(1, 0): 5, (2, 0): 3, (3, 0): 1},
            surface_terrain={
                (1, 0): "plains", (2, 0): "plains", (3, 0): "plains",
            },
            hydrology=None,
            surface_facing=None,
        )
        left = ColumnRect(x_min=1, x_max=2, y_min=0, y_max=0)
        samples, refs = sample_open_land_meter(
            surface, road_key="road", rect=left, halo=1,
        )
        seeds = {xy for xy, _, _ in samples}
        self.assertIn((2, 0), seeds)
        self.assertNotIn((3, 0), seeds)
        self.assertIn((1, 0), refs)
        self.assertNotIn((2, 0), refs)

    def test_open_land_reads_graded_halo(self) -> None:
        from app.application.worldData.generators.terrain.types import ColumnRect

        surface = MeterGradeSurface(
            surface_z={(5, 5): 8, (6, 5): 6, (7, 5): 4},
            surface_terrain={
                (5, 5): "plains", (6, 5): "plains", (7, 5): "plains",
            },
            hydrology=None,
            surface_facing=None,
            grade_uid={(6, 5): "g-left"},
        )
        late = ColumnRect(x_min=7, x_max=7, y_min=5, y_max=5)
        samples, refs = sample_open_land_meter(
            surface, road_key="road", rect=late, halo=1,
        )
        seeds = {xy for xy, _, _ in samples}
        self.assertIn((7, 5), seeds)
        self.assertNotIn((6, 5), seeds)
        self.assertIn((6, 5), refs)


class DetailedGradeGenerateTest(unittest.TestCase):
    def test_empty_without_templates(self) -> None:
        from app.application.worldData.generators.terrain.types import GridBBox, SurfaceHeightmap

        bbox = GridBBox(x_min=0, x_max=3, y_min=0, y_max=3)
        hm = SurfaceHeightmap(
            world_uid="w",
            bbox=bbox,
            surface_z={(1, 0): 5, (2, 0): 3, (0, 0): 3, (0, 1): 3},
        )
        state = TileSurfaceState(
            heightmap=hm,
            n_eff={(x, y): 1 for x in range(4) for y in range(4)},
            hydrology=None,
            surface_terrain={
                (1, 0): "plains", (2, 0): "plains",
                (0, 0): "plains", (0, 1): "plains",
            },
        )
        w = MagicMock()
        w.world_uid = "w"
        w.seed = 1
        w.terrain_masks = None
        w.terrain_registry = None
        w.relief_grade_obstacle_policy = None
        result = generate_detailed_grade(w, state, relief_templates_by_uid={})
        self.assertEqual(result.surface_grade_uid, {})
        self.assertEqual(result.grade_instances, ())

    def test_build_tile_surface_state_no_grade_from_parent(self) -> None:
        from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
        from app.dataModel.worldPack.parentLightTile import ParentLightTile
        from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire

        cells = [
            WorldMapCellWire(
                tx=0, ty=0, surface_z=5, system_terrain="plains",
                system_grade_uid="g-legacy",
            ),
        ]
        parent = ParentLightTile.from_cells(
            world_uid="w", gx=0, gy=0, side=1, tile_m=4, cells=cells,
        )
        terrain = TerrainBatchOrchestrator(MagicMock())
        w = MagicMock()
        w.world_uid = "w"
        w.map_cell_size_m = 4
        w.seed = 1
        w.z_min = -2
        w.z_max = 20
        w.map_subsurface_depth = 0
        w.terrain_registry = None
        w.terrain_masks = None
        w.terrain_scalars = None
        w.closed_planet_grid = False
        w.magma_band_thickness = None
        ctx = MagicMock()
        ctx.meter_z_overrides = {}
        ctx.sparse_meter_hydro = {}
        state = terrain.build_tile_surface_state(
            w, [], ctx, 0, 0, parent_light=parent,
        )
        self.assertIsNone(state.surface_grade_uid)

    def test_generate_stamps_with_templates(self) -> None:
        from app.application.worldData.generators.terrain.types import GridBBox, SurfaceHeightmap
        from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
        from app.dataModel.terrain.relief import ReliefTemplate
        from app.db.models.world import World

        tpl = ReliefTemplate.model_validate({
            "system_name": "open_step",
            "display_name": "Open",
            "context": "open_land",
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        uid = relief_template_uid("open_step")
        world = World(
            world_uid="w_d1",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_template_registry=[{
                "system_template_uid": uid,
                "context": "open_land",
                "display_template_name": "Open",
            }],
            relief_pick_policy={
                "open_land": {"mode": "fixed", "default_template_uid": uid},
            },
        )
        surface_z = {
            (5, 5): 8, (6, 5): 6, (7, 5): 6,
            (5, 6): 8, (6, 6): 6,
        }
        bbox = GridBBox(x_min=5, x_max=7, y_min=5, y_max=6)
        hm = SurfaceHeightmap(
            world_uid="w_d1",
            bbox=bbox,
            surface_z=surface_z,
        )
        state = TileSurfaceState(
            heightmap=hm,
            n_eff={xy: 1 for xy in surface_z},
            hydrology=None,
            surface_terrain={xy: "plains" for xy in surface_z},
        )
        result = generate_detailed_grade(
            world, state, relief_templates_by_uid={uid: tpl},
        )
        self.assertTrue(result.grade_instances)
        self.assertTrue(result.surface_grade_uid)
        stamped = {xy for inst in result.grade_instances for xy in inst.cell_refs}
        self.assertTrue(stamped)
        self.assertNotIn((5, 5), stamped)
        self.assertNotIn((5, 6), stamped)

    def test_two_rects_stitch_one_uid(self) -> None:
        from app.application.worldData.generators.terrain.types import (
            ColumnRect,
            GridBBox,
            SurfaceHeightmap,
        )
        from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
        from app.dataModel.terrain.relief import ReliefTemplate
        from app.db.models.world import World

        tpl = ReliefTemplate.model_validate({
            "system_name": "open_step",
            "display_name": "Open",
            "context": "open_land",
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        uid = relief_template_uid("open_step")
        world = World(
            world_uid="w_stitch",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_template_registry=[{
                "system_template_uid": uid,
                "context": "open_land",
                "display_template_name": "Open",
            }],
            relief_pick_policy={
                "open_land": {"mode": "fixed", "default_template_uid": uid},
            },
        )
        surface_z = {
            (5, 5): 8, (6, 5): 6, (7, 5): 4, (8, 5): 4,
            (5, 6): 8, (6, 6): 6, (7, 6): 4, (8, 6): 4,
        }
        bbox = GridBBox(x_min=5, x_max=8, y_min=5, y_max=6)
        hm = SurfaceHeightmap(world_uid="w_stitch", bbox=bbox, surface_z=surface_z)
        state = TileSurfaceState(
            heightmap=hm,
            n_eff={xy: 1 for xy in surface_z},
            hydrology=None,
            surface_terrain={xy: "plains" for xy in surface_z},
        )
        left = ColumnRect(x_min=5, x_max=6, y_min=5, y_max=6)
        right = ColumnRect(x_min=7, x_max=7, y_min=5, y_max=6)
        result = generate_detailed_grade(
            world, state,
            relief_templates_by_uid={uid: tpl},
            rects=[left, right],
        )
        self.assertTrue(result.grade_instances)
        uids = {inst.grade_uid for inst in result.grade_instances}
        self.assertEqual(len(uids), 1)
        stamped = set(result.surface_grade_uid)
        self.assertTrue({(6, 5), (6, 6)} & stamped)
        self.assertTrue({(7, 5), (7, 6)} & stamped)
        self.assertEqual(
            {result.surface_grade_uid[xy] for xy in stamped},
            uids,
        )

    def test_late_chunk_reuses_existing_uid(self) -> None:
        from app.application.worldData.generators.terrain.types import (
            ColumnRect,
            GridBBox,
            SurfaceHeightmap,
        )
        from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
        from app.dataModel.terrain.relief import ReliefTemplate
        from app.db.models.world import World

        tpl = ReliefTemplate.model_validate({
            "system_name": "open_step",
            "display_name": "Open",
            "context": "open_land",
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        uid = relief_template_uid("open_step")
        world = World(
            world_uid="w_late",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_template_registry=[{
                "system_template_uid": uid,
                "context": "open_land",
                "display_template_name": "Open",
            }],
            relief_pick_policy={
                "open_land": {"mode": "fixed", "default_template_uid": uid},
            },
        )
        surface_z = {
            (5, 5): 8, (6, 5): 6, (7, 5): 4, (8, 5): 4,
            (5, 6): 8, (6, 6): 6, (7, 6): 4, (8, 6): 4,
        }
        bbox = GridBBox(x_min=5, x_max=8, y_min=5, y_max=6)
        hm = SurfaceHeightmap(world_uid="w_late", bbox=bbox, surface_z=surface_z)
        state = TileSurfaceState(
            heightmap=hm,
            n_eff={xy: 1 for xy in surface_z},
            hydrology=None,
            surface_terrain={xy: "plains" for xy in surface_z},
        )
        first = generate_detailed_grade(
            world, state,
            relief_templates_by_uid={uid: tpl},
            rects=[ColumnRect(x_min=5, x_max=6, y_min=5, y_max=6)],
        )
        self.assertTrue(first.grade_instances)
        known = first.grade_instances[0].grade_uid
        late = generate_detailed_grade(
            world, state,
            relief_templates_by_uid={uid: tpl},
            rects=[ColumnRect(x_min=7, x_max=7, y_min=5, y_max=6)],
            existing_uids=first.surface_grade_uid,
        )
        self.assertTrue(late.grade_instances)
        self.assertEqual(late.grade_instances[0].grade_uid, known)
        late_rect = ColumnRect(x_min=7, x_max=7, y_min=5, y_max=6)
        for x, y in late.surface_grade_uid:
            self.assertTrue(late_rect.x_min <= x <= late_rect.x_max)
            self.assertTrue(late_rect.y_min <= y <= late_rect.y_max)


class DetailedGradeMaterializeTest(unittest.TestCase):
    def test_r36t_corridor_excludes_ref_cells(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeMaterialize import (
            r36t_corridor_cells,
        )

        wrote = ((1, 0), (2, 0), (3, 0))
        refs = {(1, 0)}
        self.assertEqual(r36t_corridor_cells(wrote, refs), ((2, 0), (3, 0)))

    def test_meter_grade_cell_blocked_so_t(self) -> None:
        from app.application.worldData.pack.refine.meterGradeSurface import (
            meter_grade_cell_blocked,
        )
        from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

        barriers = WorldTerrainRegistry.canonical_barrier_terrain_keys()
        wall = next(iter(barriers))
        surface = MeterGradeSurface(
            surface_z={(0, 0): 5, (1, 0): 5, (2, 0): 5, (3, 0): 5},
            surface_terrain={
                (0, 0): "plains",
                (1, 0): "road",
                (2, 0): "plains",
                (3, 0): wall,
            },
            hydrology={
                (2, 0): MapCellHydrology(role=HydrologyCellRole.LAKE),
            },
            surface_facing=None,
            grade_uid={(0, 0): "g1"},
        )
        blocked = lambda xy: meter_grade_cell_blocked(
            surface, xy, road_key="road", barrier_keys=barriers,
        )
        self.assertTrue(blocked((9, 9)))  # missing z
        self.assertTrue(blocked((0, 0)))  # graded
        self.assertTrue(blocked((1, 0)))  # road
        self.assertTrue(blocked((2, 0)))  # open water
        self.assertTrue(blocked((3, 0)))  # barrier
        surface2 = MeterGradeSurface(
            surface_z={(4, 0): 3},
            surface_terrain={(4, 0): "plains"},
            hydrology=None,
            surface_facing=None,
        )
        self.assertFalse(
            meter_grade_cell_blocked(
                surface2, (4, 0), road_key="road", barrier_keys=barriers,
            ),
        )
        river = MeterGradeSurface(
            surface_z={(5, 0): 2},
            surface_terrain={(5, 0): "plains"},
            hydrology={(5, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED)},
            surface_facing=None,
        )
        self.assertTrue(
            meter_grade_cell_blocked(
                river, (5, 0), road_key="road", barrier_keys=barriers,
            ),
        )
        self.assertTrue(HydrologyCellRole.RIVER_BED.blocks_grade_seed())
        self.assertFalse(HydrologyCellRole.SHORE.blocks_grade_seed())

    def test_inherit_uid_requires_unique_neighbor(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeMaterialize import (
            inherit_segment_uid,
        )

        surface = MeterGradeSurface(
            surface_z={},
            surface_terrain={},
            hydrology=None,
            surface_facing=None,
        )
        self.assertEqual(
            inherit_segment_uid(
                surface, ((2, 0),), existing={(1, 0): "g-one"},
            ),
            "g-one",
        )
        self.assertIsNone(
            inherit_segment_uid(
                surface,
                ((2, 0),),
                existing={(1, 0): "b-uid", (3, 0): "a-uid"},
            ),
        )

    def test_merge_cell_refs_unions_sql_and_tuples(self) -> None:
        from app.application.worldData.gradeInstanceMerge import (
            apply_prior_cell_refs,
            merge_cell_refs,
        )
        from app.dataModel.terrain.relief.enums import ReliefSideKind
        from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance

        self.assertEqual(
            merge_cell_refs([[1, 0], [2, 0]], ((2, 0), (3, 0))),
            [(1, 0), (2, 0), (3, 0)],
        )
        inst = ReliefGradeInstance(
            grade_uid="g",
            world_uid="w",
            kind=ReliefSideKind.SHEER,
            height_cells=1,
            length_cells=1,
            cell_refs=[(2, 0)],
        )
        merged = apply_prior_cell_refs(inst, [[1, 0], [2, 0]])
        self.assertEqual(list(merged.cell_refs), [(1, 0), (2, 0)])
        self.assertIs(apply_prior_cell_refs(inst, None), inst)


if __name__ == "__main__":
    unittest.main()
