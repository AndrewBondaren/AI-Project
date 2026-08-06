"""RELIEF-BAR-1: structure_refs → wall along ribbon (outside generators/terrain/relief)."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.barrier.ribbonFence import fence_cells_along_ribbon
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.ribbonBarrierApply import (
    apply_ribbon_barriers,
)
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_to_macro_local,
)
from app.application.worldData.pack.bake.lightGrid.ribbonIntent import RibbonIntent
from app.dataModel.terrain.relief.canal import StructureCanal
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.db.models.world import World


def _compose_with(
    cells: dict[tuple[int, int], tuple[str | None, int, str | None]],
    *,
    side: int = 32,
) -> tuple[LightGridCompose, set[tuple[int, int]]]:
    """cells: (lx,ly) → (terrain, z, grade_uid|None)."""
    scale = LightGridScale.from_tile(tile_m=side * 10, side=side)
    compose = LightGridCompose(scale=scale)
    tiles: set[tuple[int, int]] = set()
    for (lx, ly), (terrain, z, grade_uid) in cells.items():
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        tiles.add((gx, gy))
        cell = compose.ensure(gx, gy, tx, ty)
        cell.system_terrain = terrain
        cell.surface_z = z
        cell.system_grade_uid = grade_uid
    return compose, tiles


def _ctx(world: World, tiles: set[tuple[int, int]], intents: list[RibbonIntent]) -> LightGridBakeContext:
    scale = LightGridScale.from_tile(tile_m=320, side=32)
    ctx = LightGridBakeContext(
        world=world,
        locations=[],
        locations_index=LocationsIndexWire(),
        tiles=sorted(tiles),
        scale=scale,
    )
    ctx.ribbon_intents.extend(intents)
    return ctx


class RibbonFencePureTest(unittest.TestCase):
    def test_ortho_neighbors_only(self) -> None:
        grade = {(5, 5)}
        allowed = {(4, 5), (6, 5), (5, 4), (5, 6), (4, 4)}  # diag present but must not pick
        out = fence_cells_along_ribbon(grade, allow=lambda c: c in allowed)
        self.assertEqual(out, {(4, 5), (6, 5), (5, 4), (5, 6)})
        self.assertNotIn((4, 4), out)

    def test_skips_grade_cells(self) -> None:
        grade = {(0, 0), (1, 0)}
        out = fence_cells_along_ribbon(
            grade, allow=lambda c: True,
        )
        self.assertNotIn((0, 0), out)
        self.assertNotIn((1, 0), out)
        self.assertIn((2, 0), out)
        self.assertIn((-1, 0), out)


class RibbonBarrierApplyTest(unittest.TestCase):
    def test_paints_wall_outside_grade_not_on_road(self) -> None:
        # road (0,0); grade (1,0); free (2,0) should become wall
        cells = {
            (0, 0): ("road", 10, None),
            (1, 0): ("plains", 9, "g1"),
            (2, 0): ("plains", 8, None),
            (1, 1): ("plains", 8, None),
            (1, -1): ("plains", 8, None),
        }
        compose, tiles = _compose_with(cells)
        world = World(
            world_uid="w_bar1",
            name="W",
            created_at="2026-01-01T00:00:00Z",
        )
        intent = RibbonIntent(
            owner_uid="e1",
            site_id="e1:0",
            template_uid=None,
            kind="slope",
            width=1,
            cell_coords=((1, 0),),
            skipped=False,
            extra_structure_refs=("wooden_fence",),
        )
        ctx = _ctx(world, tiles, [intent])
        n = apply_ribbon_barriers(compose, ctx)
        self.assertGreaterEqual(n, 1)
        gx, gy, tx, ty = light_to_macro_local(2, 0, compose.scale)
        self.assertEqual(compose.get(gx, gy, tx, ty).system_terrain, "wall")
        # road untouched
        rgx, rgy, rtx, rty = light_to_macro_local(0, 0, compose.scale)
        self.assertEqual(compose.get(rgx, rgy, rtx, rty).system_terrain, "road")
        # grade cell terrain not forced to wall
        ggx, ggy, gtx, gty = light_to_macro_local(1, 0, compose.scale)
        self.assertNotEqual(compose.get(ggx, ggy, gtx, gty).system_terrain, "wall")
        self.assertEqual(compose.get(ggx, ggy, gtx, gty).system_grade_uid, "g1")

    def test_skipped_intent_no_paint(self) -> None:
        cells = {
            (1, 0): ("plains", 9, None),
            (2, 0): ("plains", 8, None),
        }
        compose, tiles = _compose_with(cells)
        world = World(
            world_uid="w_bar1_skip",
            name="W",
            created_at="2026-01-01T00:00:00Z",
        )
        intent = RibbonIntent(
            owner_uid="e1",
            site_id="e1:0",
            template_uid=None,
            kind=None,
            width=0,
            cell_coords=(),
            skipped=True,
            reason="clearance_skip",
            extra_structure_refs=("wooden_fence",),
        )
        ctx = _ctx(world, tiles, [intent])
        self.assertEqual(apply_ribbon_barriers(compose, ctx), 0)

    def test_unknown_ref_no_paint(self) -> None:
        cells = {
            (1, 0): ("plains", 9, "g1"),
            (2, 0): ("plains", 8, None),
        }
        compose, tiles = _compose_with(cells)
        world = World(
            world_uid="w_bar1_unk",
            name="W",
            created_at="2026-01-01T00:00:00Z",
        )
        intent = RibbonIntent(
            owner_uid="e1",
            site_id="e1:0",
            template_uid=None,
            kind="sheer",
            width=1,
            cell_coords=((1, 0),),
            skipped=False,
            extra_structure_refs=("not_a_real_barrier",),
        )
        ctx = _ctx(world, tiles, [intent])
        self.assertEqual(apply_ribbon_barriers(compose, ctx), 0)
        gx, gy, tx, ty = light_to_macro_local(2, 0, compose.scale)
        self.assertEqual(compose.get(gx, gy, tx, ty).system_terrain, "plains")

    def test_multi_ref_unknown_second_still_stamps(self) -> None:
        """v1: union footprint; unknown refs skipped; first resolved is enough."""
        cells = {
            (1, 0): ("plains", 9, "g1"),
            (2, 0): ("plains", 8, None),
        }
        compose, tiles = _compose_with(cells)
        world = World(
            world_uid="w_bar1_multi",
            name="W",
            created_at="2026-01-01T00:00:00Z",
        )
        intent = RibbonIntent(
            owner_uid="e1",
            site_id="e1:0",
            template_uid=None,
            kind="slope",
            width=1,
            cell_coords=((1, 0),),
            skipped=False,
            extra_structure_refs=("wooden_fence", "not_a_real_barrier"),
        )
        ctx = _ctx(world, tiles, [intent])
        n = apply_ribbon_barriers(compose, ctx)
        self.assertGreaterEqual(n, 1)
        gx, gy, tx, ty = light_to_macro_local(2, 0, compose.scale)
        self.assertEqual(compose.get(gx, gy, tx, ty).system_terrain, "wall")

    def test_structure_canal_refs_via_intent_canal(self) -> None:
        cells = {
            (1, 0): ("plains", 9, "g1"),
            (2, 0): ("plains", 8, None),
        }
        compose, tiles = _compose_with(cells)
        world = World(
            world_uid="w_bar1_canal",
            name="W",
            created_at="2026-01-01T00:00:00Z",
        )
        intent = RibbonIntent(
            owner_uid="e1",
            site_id="e1:0",
            template_uid=None,
            kind="slope",
            width=1,
            cell_coords=((1, 0),),
            skipped=False,
            canal=StructureCanal(
                system_type="lined",
                structure_refs=["stone_fence"],
            ),
        )
        self.assertEqual(intent.structure_refs, ("stone_fence",))
        ctx = _ctx(world, tiles, [intent])
        n = apply_ribbon_barriers(compose, ctx)
        self.assertGreaterEqual(n, 1)
        gx, gy, tx, ty = light_to_macro_local(2, 0, compose.scale)
        self.assertEqual(compose.get(gx, gy, tx, ty).system_terrain, "wall")


if __name__ == "__main__":
    unittest.main()

