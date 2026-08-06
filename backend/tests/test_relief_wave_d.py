"""Wave D: open_land / shore sample + ribbon apply (shared path)."""

from __future__ import annotations

import unittest

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.openLandSample import (
    sample_open_land_cells,
)
from app.application.worldData.pack.bake.lightGrid.contributors.shoreSample import (
    sample_shore_cells,
)
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_to_macro_local,
)
from app.application.worldData.pack.bake.lightGrid.maskDomainRegistry import (
    build_default_contributors,
)
from app.application.worldData.reliefTemplateLibraryService import relief_template_uid
from app.dataModel.masks.enums.maskDomainId import (
    COMPOSE_CONTRIBUTOR_ORDER,
    LightContributorId,
)
from app.dataModel.terrain.relief import ReliefTemplate
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.db.models.world import World


def _compose_cells(
    cells: dict[tuple[int, int], dict],
    *,
    side: int = 32,
) -> tuple[LightGridCompose, set[tuple[int, int]]]:
    scale = LightGridScale.from_tile(tile_m=side * 10, side=side)
    compose = LightGridCompose(scale=scale)
    tiles: set[tuple[int, int]] = set()
    for (lx, ly), props in cells.items():
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        tiles.add((gx, gy))
        cell = compose.ensure(gx, gy, tx, ty)
        cell.system_terrain = props.get("terrain")
        cell.surface_z = int(props.get("z", 0))
        cell.system_grade_uid = props.get("grade_uid")
        role = props.get("hydro")
        if role is not None:
            cell.hydrology_role = role
    return compose, tiles


class ComposeOrderWaveDTest(unittest.TestCase):
    def test_open_land_shore_before_road(self) -> None:
        order = list(COMPOSE_CONTRIBUTOR_ORDER)
        self.assertLess(
            order.index(LightContributorId.OPEN_LAND),
            order.index(LightContributorId.SHORE),
        )
        self.assertLess(
            order.index(LightContributorId.SHORE),
            order.index(LightContributorId.ROAD),
        )
        self.assertLess(
            order.index(LightContributorId.ROAD),
            order.index(LightContributorId.ROAD_SHOULDER),
        )
        self.assertLess(
            order.index(LightContributorId.HYDRO),
            order.index(LightContributorId.OPEN_LAND),
        )
        names = tuple(c.name for c in build_default_contributors())
        self.assertEqual(names, tuple(cid.value for cid in COMPOSE_CONTRIBUTOR_ORDER))


class OpenLandSampleTest(unittest.TestCase):
    def test_downhill_seed_uphill_ref(self) -> None:
        # (1,0) high plains z=5; (2,0) low plains z=3 → seed at (2,0), ref (1,0)
        cells = {
            (1, 0): {"terrain": "plains", "z": 5},
            (2, 0): {"terrain": "plains", "z": 3},
            (0, 0): {"terrain": "plains", "z": 5},
        }
        compose, tiles = _compose_cells(cells)
        samples, refs = sample_open_land_cells(
            compose, tile_set=tiles, road_key="road",
        )
        seeds = {xy for xy, _, _ in samples}
        self.assertIn((2, 0), seeds)
        self.assertIn((1, 0), refs)
        dz_by_seed = {xy: dz for xy, _, dz in samples}
        self.assertEqual(dz_by_seed[(2, 0)], 2)

    def test_skips_graded_and_road(self) -> None:
        cells = {
            (1, 0): {"terrain": "plains", "z": 5},
            (2, 0): {"terrain": "plains", "z": 3, "grade_uid": "g1"},
            (3, 0): {"terrain": "road", "z": 4},
            (4, 0): {"terrain": "plains", "z": 2},
        }
        compose, tiles = _compose_cells(cells)
        samples, _ = sample_open_land_cells(
            compose, tile_set=tiles, road_key="road",
        )
        seeds = {xy for xy, _, _ in samples}
        self.assertNotIn((2, 0), seeds)
        # (4,0) low next to road (3,0) — road not in land map as high, no sample from road
        self.assertNotIn((4, 0), seeds)


class ShoreSampleTest(unittest.TestCase):
    def test_landward_of_shore_role(self) -> None:
        cells = {
            (1, 0): {"terrain": "shore", "z": 2, "hydro": WorldMapHydrologyRole.SHORE},
            (2, 0): {"terrain": "plains", "z": 4},
            (0, 0): {"terrain": "liquid_body", "z": 0, "hydro": WorldMapHydrologyRole.LAKE},
        }
        compose, tiles = _compose_cells(cells)
        samples, refs = sample_shore_cells(
            compose, tile_set=tiles, road_key="road",
        )
        seeds = {xy for xy, _, _ in samples}
        self.assertIn((2, 0), seeds)
        self.assertIn((1, 0), refs)
        self.assertNotIn((0, 0), seeds)


class OpenLandApplySmokeTest(unittest.TestCase):
    def test_apply_stamps_when_template_present(self) -> None:
        from app.application.worldData.pack.bake.lightGrid.contributors.openLandApply import (
            apply_open_land_grades,
        )

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
        cells = {
            (5, 5): {"terrain": "plains", "z": 8},
            (6, 5): {"terrain": "plains", "z": 6},
            (7, 5): {"terrain": "plains", "z": 6},
            (5, 6): {"terrain": "plains", "z": 8},
            (6, 6): {"terrain": "plains", "z": 6},
        }
        compose, tiles = _compose_cells(cells)
        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(),
            tiles=sorted(tiles),
            scale=compose.scale,
            relief_templates_by_uid={uid: tpl},
        )
        intents = apply_open_land_grades(compose, ctx)
        self.assertTrue(intents)
        applied = [i for i in intents if not i.skipped]
        self.assertTrue(applied)


if __name__ == "__main__":
    unittest.main()
