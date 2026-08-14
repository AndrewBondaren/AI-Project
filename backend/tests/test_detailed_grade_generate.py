"""Tests for R36u detailed grade generate on meter grid."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.application.worldData.pack.refine.detailedGradeGenerate import generate_detailed_grade
from app.application.worldData.pack.refine.detailedGradeSample import (
    sample_open_land_meter,
    sample_road_shoulder_meter,
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

    def test_road_shoulder_land_beside_road(self) -> None:
        surface = MeterGradeSurface(
            surface_z={(1, 0): 5, (2, 0): 3},
            surface_terrain={(1, 0): "road", (2, 0): "plains"},
            hydrology=None,
            surface_facing=None,
        )
        samples, refs = sample_road_shoulder_meter(surface, road_key="road")
        self.assertEqual(samples, [((2, 0), "plains", 2)])
        self.assertEqual(refs, {(1, 0)})

    def test_road_shoulder_skips_flat(self) -> None:
        surface = MeterGradeSurface(
            surface_z={(1, 0): 5, (2, 0): 5},
            surface_terrain={(1, 0): "road", (2, 0): "plains"},
            hydrology=None,
            surface_facing=None,
        )
        samples, refs = sample_road_shoulder_meter(surface, road_key="road")
        self.assertEqual(samples, [])
        self.assertEqual(refs, set())


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
        result = generate_detailed_grade(
            w, state, relief_templates_by_uid={}, tile_gx=0, tile_gy=0,
        )
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
            tile_gx=0, tile_gy=0,
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
            terrain_chunk_columns=2,
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
            tile_gx=0, tile_gy=0,
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
            terrain_chunk_columns=2,
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
            tile_gx=0, tile_gy=0,
        )
        self.assertTrue(first.grade_instances)
        known = first.grade_instances[0].grade_uid
        late = generate_detailed_grade(
            world, state,
            relief_templates_by_uid={uid: tpl},
            rects=[ColumnRect(x_min=7, x_max=7, y_min=5, y_max=6)],
            existing_uids=first.surface_grade_uid,
            tile_gx=0, tile_gy=0,
        )
        self.assertTrue(late.grade_instances)
        self.assertEqual(late.grade_instances[0].grade_uid, known)
        late_rect = ColumnRect(x_min=7, x_max=7, y_min=5, y_max=6)
        for x, y in late.surface_grade_uid:
            self.assertTrue(late_rect.x_min <= x <= late_rect.x_max)
            self.assertTrue(late_rect.y_min <= y <= late_rect.y_max)

    def test_two_tile_bakes_along_seam_one_uid(self) -> None:
        """R36w edge: two independent bakes, Δz along the owner face → one uid.

        Seeds sit on the shared vertical columns (toe on the rim, crest one
        cell inward). Interior y so a corner cell's second rim face is not
        the SoT. Open rim: face has < 2 chunk parents on this tile → void
        beyond is not a C18 obstacle.
        """
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
            world_uid="w_seam",
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
            terrain_chunk_columns=2,
        )
        templates = {uid: tpl}

        def _state(z: dict, x0: int, x1: int) -> TileSurfaceState:
            ys = {xy[1] for xy in z}
            bbox = GridBBox(x_min=x0, x_max=x1, y_min=min(ys), y_max=max(ys))
            return TileSurfaceState(
                heightmap=SurfaceHeightmap(
                    world_uid="w_seam", bbox=bbox, surface_z=z,
                ),
                n_eff={xy: 1 for xy in z},
                hydrology=None,
                surface_terrain={xy: "plains" for xy in z},
            )

        west_z = {
            (x, y): (6 if x == 3 else 8)
            for x in range(4) for y in range(4)
        }
        east_z = {
            (x, y): (6 if x == 4 else 8)
            for x in range(4, 8) for y in range(4)
        }
        west = generate_detailed_grade(
            world, _state(west_z, 0, 3),
            relief_templates_by_uid=templates,
            tile_gx=0, tile_gy=0, chunk_size=2,
        )
        east = generate_detailed_grade(
            world, _state(east_z, 4, 7),
            relief_templates_by_uid=templates,
            tile_gx=1, tile_gy=0, chunk_size=2,
        )
        self.assertTrue(west.grade_instances)
        self.assertTrue(east.grade_instances)
        self.assertIn((3, 1), west.surface_grade_uid)
        self.assertIn((4, 1), east.surface_grade_uid)
        self.assertEqual(
            west.surface_grade_uid[(3, 1)],
            east.surface_grade_uid[(4, 1)],
        )
        self.assertIn((3, 2), west.surface_grade_uid)
        self.assertIn((4, 2), east.surface_grade_uid)
        self.assertEqual(
            west.surface_grade_uid[(3, 2)],
            east.surface_grade_uid[(4, 2)],
        )

    def test_across_seam_halo_reads_neighbor_z(self) -> None:
        """Δz only across the grid seam: halo overlay binds the shared rim uid."""
        from app.application.worldData.generators.terrain.types import GridBBox, SurfaceHeightmap
        from app.application.worldData.pack.refine.detailedGradeCatalog import (
            FaceKey,
            build_tile_face_catalog,
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
            world_uid="w_halo",
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
            terrain_chunk_columns=2,
        )
        templates = {uid: tpl}

        def _state(z: dict, x0: int, x1: int) -> TileSurfaceState:
            ys = {xy[1] for xy in z}
            bbox = GridBBox(x_min=x0, x_max=x1, y_min=min(ys), y_max=max(ys))
            return TileSurfaceState(
                heightmap=SurfaceHeightmap(
                    world_uid="w_halo", bbox=bbox, surface_z=z,
                ),
                n_eff={xy: 1 for xy in z},
                hydrology=None,
                surface_terrain={xy: "plains" for xy in z},
            )

        west_state = _state(
            {(x, y): 8 for x in range(4) for y in range(4)}, 0, 3,
        )
        east_state = _state(
            {(x, y): 6 for x in range(4, 8) for y in range(4)}, 4, 7,
        )
        bare = generate_detailed_grade(
            world, east_state,
            relief_templates_by_uid=templates,
            tile_gx=1, tile_gy=0, chunk_size=2,
        )
        self.assertFalse(bare.surface_grade_uid)

        east = generate_detailed_grade(
            world, east_state,
            relief_templates_by_uid=templates,
            tile_gx=1, tile_gy=0, chunk_size=2,
            halo_neighbors=(west_state,),
        )
        self.assertIn((4, 1), east.surface_grade_uid)
        west_cat = build_tile_face_catalog(
            world_seed="w_halo", tile_gx=0, tile_gy=0,
            origin_x=0, origin_y=0, tile_w=4, tile_h=4, chunk_size=2,
        )
        east_cat = build_tile_face_catalog(
            world_seed="w_halo", tile_gx=1, tile_gy=0,
            origin_x=4, origin_y=0, tile_w=4, tile_h=4, chunk_size=2,
        )
        shared = west_cat.uid_for_face(FaceKey("V", 1, 0))
        self.assertEqual(shared, east_cat.uid_for_face(FaceKey("V", -1, 0)))
        self.assertEqual(east.surface_grade_uid[(4, 1)], shared)

    def test_two_tile_road_shoulder_along_seam_one_uid(self) -> None:
        from app.application.worldData.generators.terrain.types import GridBBox, SurfaceHeightmap
        from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
        from app.dataModel.terrain.relief import ReliefTemplate
        from app.dataModel.terrain.relief.enums import ReliefContext
        from app.db.models.world import World

        tpl = ReliefTemplate.model_validate({
            "system_name": "intercity_shoulder",
            "display_name": "Shoulder",
            "context": ReliefContext.ROAD_SHOULDER.value,
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        uid = relief_template_uid("intercity_shoulder")
        world = World(
            world_uid="w_road_seam",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_template_registry=[{
                "system_template_uid": uid,
                "context": ReliefContext.ROAD_SHOULDER.value,
                "display_template_name": "Shoulder",
            }],
            relief_pick_policy={
                ReliefContext.ROAD_SHOULDER.value: {
                    "mode": "fixed", "default_template_uid": uid,
                },
            },
            terrain_chunk_columns=2,
        )
        templates = {uid: tpl}

        def _state(
            z: dict, terrain: dict, x0: int, x1: int,
        ) -> TileSurfaceState:
            ys = {xy[1] for xy in z}
            bbox = GridBBox(x_min=x0, x_max=x1, y_min=min(ys), y_max=max(ys))
            return TileSurfaceState(
                heightmap=SurfaceHeightmap(
                    world_uid="w_road_seam", bbox=bbox, surface_z=z,
                ),
                n_eff={xy: 1 for xy in z},
                hydrology=None,
                surface_terrain=terrain,
            )

        west_z = {(x, y): 6 for x in range(4) for y in range(4)}
        west_t = {(x, y): "plains" for x in range(4) for y in range(4)}
        for x in range(3):
            for y in range(4):
                west_z[(x, y)] = 8
                west_t[(x, y)] = "road"
        east_z = {(x, y): 6 for x in range(4, 8) for y in range(4)}
        east_t = {(x, y): "plains" for x in range(4, 8) for y in range(4)}
        for x in range(5, 8):
            for y in range(4):
                east_z[(x, y)] = 8
                east_t[(x, y)] = "road"
        west = generate_detailed_grade(
            world, _state(west_z, west_t, 0, 3),
            relief_templates_by_uid=templates,
            tile_gx=0, tile_gy=0, chunk_size=2,
        )
        east = generate_detailed_grade(
            world, _state(east_z, east_t, 4, 7),
            relief_templates_by_uid=templates,
            tile_gx=1, tile_gy=0, chunk_size=2,
        )
        self.assertTrue(west.grade_instances)
        self.assertTrue(east.grade_instances)
        self.assertIn((3, 1), west.surface_grade_uid)
        self.assertIn((4, 1), east.surface_grade_uid)
        self.assertEqual(
            west.surface_grade_uid[(3, 1)],
            east.surface_grade_uid[(4, 1)],
        )
        self.assertEqual(
            {inst.owner_uid for inst in west.grade_instances},
            {ReliefContext.ROAD_SHOULDER.value},
        )


class DetailedGradeCatalogTest(unittest.TestCase):
    def test_shared_face_uid_agrees_both_chunks(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeCatalog import (
            FaceKey,
            build_tile_face_catalog,
        )

        cat = build_tile_face_catalog(
            world_seed="s1",
            tile_gx=0, tile_gy=0,
            origin_x=0, origin_y=0,
            tile_w=4, tile_h=2, chunk_size=2,
        )
        self.assertEqual(cat.n_cx, 2)
        self.assertEqual(
            cat.uid_for_face(FaceKey("V", 0, 0)),
            cat.uid_for_face(FaceKey("V", 0, 0)),
        )
        self.assertIn(FaceKey("V", 0, 0), cat.faces_for_cell(1, 0))
        self.assertIn(FaceKey("V", 0, 0), cat.faces_for_cell(2, 0))

    def test_inter_tile_west_face_uses_owner_tile(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeCatalog import (
            FaceKey,
            build_tile_face_catalog,
        )

        west = build_tile_face_catalog(
            world_seed="s1", tile_gx=0, tile_gy=0,
            origin_x=0, origin_y=0, tile_w=4, tile_h=2, chunk_size=2,
        )
        east = build_tile_face_catalog(
            world_seed="s1", tile_gx=1, tile_gy=0,
            origin_x=4, origin_y=0, tile_w=4, tile_h=2, chunk_size=2,
        )
        self.assertEqual(
            west.uid_for_face(FaceKey("V", 1, 0)),
            east.uid_for_face(FaceKey("V", -1, 0)),
        )
        self.assertEqual(
            west.uid_for_faces(west.faces_for_cell(3, 0), axis="V"),
            east.uid_for_faces(east.faces_for_cell(4, 0), axis="V"),
        )

    def test_uid_for_faces_prefers_tile_rim(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeCatalog import (
            FaceKey,
            build_tile_face_catalog,
        )

        cat = build_tile_face_catalog(
            world_seed="s1", tile_gx=0, tile_gy=0,
            origin_x=0, origin_y=0, tile_w=4, tile_h=4, chunk_size=2,
        )
        faces = cat.faces_for_cell(3, 1)
        self.assertIn(FaceKey("V", 1, 0), faces)
        self.assertIn(FaceKey("H", 1, 0), faces)
        self.assertTrue(cat.is_tile_rim_face(FaceKey("V", 1, 0)))
        self.assertTrue(cat.is_internal_face(FaceKey("H", 1, 0)))
        self.assertEqual(
            cat.uid_for_faces(faces, axis="V"),
            cat.uid_for_face(FaceKey("V", 1, 0)),
        )

    def test_uid_for_faces_axis_keeps_internal_stitch(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeCatalog import (
            FaceKey,
            build_tile_face_catalog,
        )

        cat = build_tile_face_catalog(
            world_seed="s1", tile_gx=0, tile_gy=0,
            origin_x=5, origin_y=5, tile_w=4, tile_h=2, chunk_size=2,
        )
        faces = cat.faces_for_cell(6, 5)
        self.assertIn(FaceKey("V", 0, 0), faces)
        self.assertTrue(any(cat.is_tile_rim_face(f) for f in faces))
        self.assertEqual(
            cat.uid_for_faces(faces, axis="V"),
            cat.uid_for_face(FaceKey("V", 0, 0)),
        )

    def test_chunk_parent_count_rim_vs_internal(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeCatalog import (
            FaceKey,
            build_tile_face_catalog,
        )

        cat = build_tile_face_catalog(
            world_seed="s1", tile_gx=0, tile_gy=0,
            origin_x=0, origin_y=0, tile_w=4, tile_h=4, chunk_size=2,
        )
        internal = FaceKey("V", 0, 0)
        rim = FaceKey("V", 1, 0)
        self.assertEqual(cat.chunk_parent_count(internal), 2)
        self.assertEqual(cat.chunk_parent_count(rim), 1)
        self.assertEqual(
            cat.chunk_parent_uids(rim),
            (cat.job_uid_chunk(1, 0),),
        )
        self.assertTrue(cat.is_open_rim_step((3, 1), (1, 0)))
        self.assertFalse(cat.is_open_rim_step((1, 1), (1, 0)))

    def test_job_uids_tile_is_l0_chunk_is_suffix(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeCatalog import (
            build_tile_face_catalog,
        )
        from app.application.worldData.pack.refine.detailedJobUid import (
            tile_edge_job_uid,
        )
        from app.dataModel.spatial.facing import COMPACT_LETTER, Facing
        from app.dataModel.worldPack.packJobUid import PackJobUid

        wire = PackJobUid.canonical_defaults()
        cat = build_tile_face_catalog(
            world_seed="seed-a", tile_gx=2, tile_gy=-1,
            origin_x=0, origin_y=0, tile_w=2, tile_h=2, chunk_size=2,
        )
        tile_uid = wire.tile_uid(world_seed="seed-a", tile_gx=2, tile_gy=-1)
        self.assertEqual(cat.macro_tile_uid(), tile_uid)
        self.assertEqual(
            cat.job_uid_chunk(0, 0),
            wire.chunk_uid(
                world_seed="seed-a", tile_gx=2, tile_gy=-1, cx=0, cy=0,
            ),
        )
        east_of_west = tile_edge_job_uid(
            world_seed="seed-a", tile_gx=2, tile_gy=-1, side=Facing.EAST,
        )
        west_of_east = tile_edge_job_uid(
            world_seed="seed-a", tile_gx=3, tile_gy=-1, side=Facing.WEST,
        )
        self.assertEqual(cat.job_uid_tile_edge(Facing.EAST), east_of_west)
        self.assertEqual(east_of_west, west_of_east)
        self.assertEqual(
            east_of_west,
            wire.tile_edge_uid(
                world_seed="seed-a",
                owner_gx=2,
                owner_gy=-1,
                compact_side=COMPACT_LETTER[Facing.EAST],
            ),
        )


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
