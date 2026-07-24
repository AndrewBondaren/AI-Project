"""MaskDomain materialize + mountain Spec pipeline (MLB-13)."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.mountains.materializer import (
    MountainMaskMaterializer,
)
from app.application.worldData.generators.terrain.mountains.formPipeline import (
    materialize_mountain_spec,
)
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.masks.mergeDeclare import merge_declare_over_auto
from app.application.worldData.masks.runMaskDomain import run_mask_domain
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.terrainMasks import (
    MountainFormBySides,
    MountainKind,
    MountainSpec,
    WorldTerrainMasks,
)
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from types import SimpleNamespace


def _world(**overrides):
    base = dict(
        world_uid="world-mask-mat",
        map_cell_size_m=1000,
        world_map_cells_per_tile=None,
        z_min=0,
        z_max=8,
        map_subsurface_depth=0,
        terrain_masks={},
        terrain_registry=[
            {"system_terrain": "plains", "display_name": "Plains"},
            {"system_terrain": "mountain", "display_name": "Mountain"},
        ],
        climate_zone_registry=None,
        hydrology={"enabled": False},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestMergeDeclare(unittest.TestCase):
    def test_declare_wins(self) -> None:
        a = MountainSpec(origin_x_m=0, origin_y_m=0, radius_m=100, location_uid="a")
        b = MountainSpec(origin_x_m=0, origin_y_m=0, radius_m=100, location_uid="a")
        c = MountainSpec(origin_x_m=10, origin_y_m=10, radius_m=100)
        merged = merge_declare_over_auto([a], [b, c], key=lambda s: s.identity_key())
        self.assertEqual(len(merged), 2)
        self.assertIs(merged[0], a)


class TestMountainMaterialize(unittest.TestCase):
    def test_footprint_nonempty(self) -> None:
        scale = LightGridScale.from_tile(1000, 32)
        spec = MountainSpec(
            origin_x_m=500,
            origin_y_m=500,
            radius_m=400,
            kind=MountainKind.ROCKY,
            form=MountainFormBySides(side_count=6),
        )
        fp = materialize_mountain_spec(spec, scale)
        self.assertGreater(len(fp.cells), 0)
        self.assertTrue(all(ref in fp.elevation_fraction for ref in fp.cells))

    def test_declared_spec_paints_via_engine(self) -> None:
        world = _world(
            terrain_masks={
                "default_mountains": {"autoresolve": False},
                "declared_mountains": [
                    {
                        "entry_type": "mountain",
                        "origin_x_m": 500,
                        "origin_y_m": 500,
                        "radius_m": 400,
                        "kind": "rocky",
                        "form": {"form_type": "by_sides", "side_count": 6},
                    }
                ],
            },
        )
        scale = LightGridScale.from_tile(1000, 32)
        compose = LightGridCompose(scale=scale)
        compose.ensure(0, 0, 16, 16).surface_z = 1
        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
        )
        n = run_mask_domain(compose, ctx, MountainMaskMaterializer())
        self.assertEqual(n, 1)
        cells = compose.to_wire_tile(0, 0)
        self.assertGreater(sum(1 for c in cells if c.system_terrain == "mountain"), 0)


class TestSpecSourcesP0(unittest.TestCase):
    def test_load_declared_excludes_geo_anchors(self) -> None:
        from app.dataModel.locations.enums.geographicSubtype import (
            GEOGRAPHIC_LOCATION_TYPE,
            GeographicSubtype,
        )
        from app.db.models.namedLocation import NamedLocation

        world = _world(
            terrain_masks={
                "default_mountains": {"autoresolve": False},
                "declared_mountains": [
                    {
                        "entry_type": "mountain",
                        "origin_x_m": 100,
                        "origin_y_m": 100,
                        "radius_m": 200,
                    }
                ],
            },
        )
        loc = NamedLocation(
            location_uid="peak-1",
            world_uid=world.world_uid,
            display_name="Peak",
            system_location_type=GEOGRAPHIC_LOCATION_TYPE,
            system_location_subtype=GeographicSubtype.PEAK.value,
            map_x=500,
            map_y=500,
            created_at="2026-01-01T00:00:00Z",
        )
        scale = LightGridScale.from_tile(1000, 32)
        ctx = LightGridBakeContext(
            world=world,
            locations=[loc],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
        )
        mat = MountainMaskMaterializer()
        declared = mat.load_declared(ctx)
        anchors = mat.load_anchor_specs(ctx)
        self.assertEqual(len(declared), 1)
        self.assertEqual(declared[0].origin_x_m, 100)
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0].location_uid, "peak-1")
        from app.application.jsonValidation import terrain_masks as read_tm

        policy = mat.category_policy(read_tm(world))
        self.assertFalse(policy.autoresolve)
        collected = mat.collect(ctx, policy)
        self.assertEqual(len(collected), 2)


class TestMaskFootprintTyped(unittest.TestCase):
    def test_rejects_orphan_fraction_keys(self) -> None:
        ref = LightCellRef(0, 0, 1, 1)
        with self.assertRaises(ValueError):
            MaskFootprint(cells=frozenset(), elevation_fraction={ref: 1.0})


class TestWorldTerrainMasksDeclared(unittest.TestCase):
    def test_declared_mountains_roundtrip(self) -> None:
        masks = WorldTerrainMasks.model_validate(
            {
                "declared_mountains": [
                    {
                        "entry_type": "mountain",
                        "origin_x_m": 1,
                        "origin_y_m": 2,
                        "radius_m": 300,
                    }
                ]
            }
        )
        self.assertEqual(len(masks.declared_mountains), 1)
        spec = masks.declared_mountains[0]
        assert isinstance(spec, MountainSpec)
        self.assertEqual(spec.origin_x_m, 1)
        self.assertEqual(len(spec.resolved_sides()), 6)


class TestQ3ACoarseFormRaster(unittest.TestCase):
    def test_macro_footprint_uses_form_not_disk(self) -> None:
        from app.application.worldData.generators.terrain.mountains.formPipeline import (
            coarse_footprint_for_spec,
        )
        from app.application.worldData.masks.rasterDisk import raster_disk
        from app.dataModel.terrainMasks import StarForm

        # Star is concave — disk over-covers; FormRaster should be a proper subset.
        spec = MountainSpec(
            origin_x_m=5000,
            origin_y_m=5000,
            radius_m=2000,
            form=StarForm(rays=5, inner_ratio=0.35),
        )
        cell_m = 500
        form_keys = set(coarse_footprint_for_spec(spec, cell_m=cell_m, light_m=31).keys())
        cx = spec.origin_x_m // cell_m
        cy = spec.origin_y_m // cell_m
        disk_keys = raster_disk(cx, cy, max(0, int(round(spec.radius_m / cell_m))))
        self.assertGreater(len(form_keys), 0)
        self.assertTrue(form_keys.issubset(disk_keys) or form_keys != disk_keys)
        # At least: not identical to a filled disk of same radius (star punches gaps).
        self.assertNotEqual(form_keys, disk_keys)

    def test_coarse_edge_fraction_below_one(self) -> None:
        from app.application.worldData.generators.terrain.mountains.formPipeline import (
            coarse_footprint_for_spec,
        )

        spec = MountainSpec(
            origin_x_m=2500,
            origin_y_m=2500,
            radius_m=2000,
            form=MountainFormBySides(side_count=6),
        )
        fp = coarse_footprint_for_spec(spec, cell_m=500, light_m=31)
        self.assertGreater(len(fp), 1)
        self.assertTrue(any(f > 0.85 for f in fp.values()))
        self.assertTrue(any(f < 0.5 for f in fp.values()))


class TestRangeSideFill(unittest.TestCase):
    def test_left_sheer_right_slope_asymmetric(self) -> None:
        from app.application.worldData.generators.terrain.mountains.rangeSideFill import (
            range_side_fraction_at_xy,
        )
        from app.dataModel.terrainMasks import (
            MountainRangeSides,
            MountainRangeSpec,
            MountainSideKind,
            MountainSideSpec,
        )

        sides = MountainRangeSides(
            left=MountainSideSpec(kind=MountainSideKind.SHEER, sheer_band_light=1),
            right=MountainSideSpec(kind=MountainSideKind.SLOPE),
        )
        spec = MountainRangeSpec(
            spine=[(0, 0), (2000, 0)],
            width_m=1000,
            sides=sides,
        )
        half = 500.0
        light_m = 31.0
        # Point near left boundary (y>0 with spine along +x → left = +y)
        left_frac = range_side_fraction_at_xy(
            1000.0, 480.0,
            spine=list(spec.spine),
            half_width_m=half,
            sides=sides,
            light_m=light_m,
        )
        right_frac = range_side_fraction_at_xy(
            1000.0, -480.0,
            spine=list(spec.spine),
            half_width_m=half,
            sides=sides,
            light_m=light_m,
        )
        self.assertIsNotNone(left_frac)
        self.assertIsNotNone(right_frac)
        # SHEER near outer edge → 0; SLOPE near outer → small but smooth > 0 typically
        self.assertEqual(left_frac, 0.0)
        self.assertGreater(right_frac, 0.0)

    def test_range_materialize_light_nonempty(self) -> None:
        from app.application.worldData.generators.terrain.mountains.formPipeline import (
            materialize_mountain_range,
        )
        from app.dataModel.terrainMasks import MountainRangeSpec

        scale = LightGridScale.from_tile(1000, 32)
        spec = MountainRangeSpec(
            spine=[(100, 500), (900, 500)],
            width_m=400,
        )
        fp = materialize_mountain_range(spec, scale)
        self.assertGreater(len(fp.cells), 0)


if __name__ == "__main__":
    unittest.main()
