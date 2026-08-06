"""Unit: Q6 / Wave B1 — shoulder sample on road footprint outer ring."""

from __future__ import annotations

import unittest

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import dilate
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderApply import (
    apply_road_shoulder_grades,
)
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderSample import (
    sample_shoulder_cells,
)
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_to_macro_local,
)
from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
from app.dataModel.terrain.relief import ReliefTemplate
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.db.models.world import World


def _compose_with(
    cells: dict[tuple[int, int], tuple[str, int]],
    *,
    side: int = 32,
) -> tuple[LightGridCompose, set[tuple[int, int]]]:
    scale = LightGridScale.from_tile(tile_m=side * 10, side=side)
    compose = LightGridCompose(scale=scale)
    tiles: set[tuple[int, int]] = set()
    for (lx, ly), (terrain, z) in cells.items():
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        tiles.add((gx, gy))
        cell = compose.ensure(gx, gy, tx, ty)
        cell.system_terrain = terrain
        cell.surface_z = z
    return compose, tiles


class RoadShoulderSampleTest(unittest.TestCase):
    def test_r0_outer_ring_around_axis(self) -> None:
        ordered = [(2, 2), (3, 2), (4, 2)]
        road = set(ordered)
        terrain_cells = {
            **{c: ("road", 5) for c in ordered},
            (2, 1): ("plains", 3),
            (2, 3): ("plains", 3),
            (3, 1): ("plains", 3),
            (3, 3): ("plains", 3),
            (4, 1): ("plains", 3),
            (4, 3): ("plains", 3),
            (1, 2): ("plains", 3),
            (5, 2): ("plains", 3),
        }
        compose, tiles = _compose_with(terrain_cells)
        samples = sample_shoulder_cells(compose, road, tile_set=tiles)
        seeds = {xy for xy, _, _ in samples}
        self.assertTrue(seeds)
        self.assertTrue(seeds.isdisjoint(road))
        for sx, sy in seeds:
            self.assertTrue(
                any((sx + dx, sy + dy) in road for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))),
            )
        self.assertEqual(samples, sorted(samples, key=lambda item: item[0]))

    def test_dilate_seeds_on_outer_ring_not_inside_footprint(self) -> None:
        ordered = [(5, 5), (6, 5), (7, 5)]
        road = dilate(set(ordered), 1)
        # Old centerline ortho (e.g. (5,6)) stays inside dilated road → must not be seeds.
        self.assertIn((5, 6), road)
        cells: dict[tuple[int, int], tuple[str, int]] = {
            c: ("road", 8) for c in road
        }
        # Paint a band around the dilated footprint.
        for lx in range(3, 10):
            for ly in range(3, 8):
                if (lx, ly) not in road:
                    cells[(lx, ly)] = ("plains", 4)
        compose, tiles = _compose_with(cells)
        samples = sample_shoulder_cells(compose, road, tile_set=tiles)
        seeds = {xy for xy, _, _ in samples}
        self.assertTrue(seeds)
        self.assertTrue(seeds.isdisjoint(road))
        # Centerline-adjacent cell inside dilate is not a seed.
        self.assertNotIn((5, 6), seeds)
        # Outer-ring cell immediately outside footprint is a seed.
        self.assertIn((5, 7), seeds)
        for seed in seeds:
            self.assertTrue(
                any(
                    (seed[0] + dx, seed[1] + dy) in road
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                ),
            )

    def test_dz_from_abutment_edge_cell(self) -> None:
        road = {(1, 1)}
        cells = {
            (1, 1): ("road", 10),
            (2, 1): ("plains", 7),
        }
        compose, tiles = _compose_with(cells)
        samples = sample_shoulder_cells(compose, road, tile_set=tiles)
        by_xy = {xy: (terrain, dz) for xy, terrain, dz in samples}
        self.assertIn((2, 1), by_xy)
        self.assertEqual(by_xy[(2, 1)], ("plains", 3))

    def test_stable_order_and_dedup(self) -> None:
        road = {(1, 1), (2, 1)}
        cells = {
            (1, 1): ("road", 5),
            (2, 1): ("road", 9),
            (1, 0): ("plains", 1),
            (2, 0): ("plains", 1),
            (0, 1): ("plains", 1),
            (3, 1): ("plains", 1),
            (1, 2): ("plains", 1),
            (2, 2): ("plains", 1),
        }
        compose, tiles = _compose_with(cells)
        a = sample_shoulder_cells(compose, road, tile_set=tiles)
        b = sample_shoulder_cells(compose, set(reversed(list(road))), tile_set=tiles)
        self.assertEqual(a, b)
        seeds = [xy for xy, _, _ in a]
        self.assertEqual(len(seeds), len(set(seeds)))
        self.assertEqual(seeds, sorted(seeds))

    def test_apply_smoke_dilated_footprint_not_empty(self) -> None:
        tpl = ReliefTemplate.model_validate({
            "system_name": "intercity_shoulder",
            "display_name": "Shoulder",
            "context": "road_shoulder",
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 0.0, "sheer_weight": 1.0},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        uid = relief_template_uid("intercity_shoulder")
        world = World(
            world_uid="w1",
            name="W",
            created_at="2026-01-01T00:00:00Z",
            relief_template_registry=[{
                "system_template_uid": uid,
                "context": "road_shoulder",
                "display_template_name": "Shoulder",
            }],
            relief_pick_policy={
                "road_shoulder": {"mode": "fixed", "default_template_uid": uid},
            },
        )
        ordered = [(5, 5), (6, 5), (7, 5)]
        road = dilate(set(ordered), 1)
        cells: dict[tuple[int, int], tuple[str, int]] = {c: ("road", 8) for c in road}
        for lx in range(3, 10):
            for ly in range(3, 8):
                if (lx, ly) not in road:
                    cells[(lx, ly)] = ("plains", 4)
        compose, tiles = _compose_with(cells)
        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=sorted(tiles),
            scale=compose.scale,
            relief_templates_by_uid={uid: tpl},
        )
        intents = apply_road_shoulder_grades(
            compose, ctx, edge_uid="e1", road_cells=road,
        )
        self.assertTrue(intents)
        self.assertTrue(ctx.road_shoulder_intents)


if __name__ == "__main__":
    unittest.main()
