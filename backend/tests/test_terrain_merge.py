"""Registry-driven rank in all shared light-cell terrain writers."""

import unittest
from types import SimpleNamespace

from app.application.worldData.masks.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.masks.terrainMerge import (
    PRESERVE_HYDROLOGY_ROLES, may_paint_terrain, terrain_merge_rank,
)
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.contributors.landcover import LandcoverContributor
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.lightGrid.paintTerrain import (
    paint_system_terrain, paint_system_terrain_cell,
)
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexWire


class TerrainMergeTests(unittest.TestCase):
    def setUp(self):
        self.registry = WorldTerrainRegistry.canonical_defaults()
        self.road_key = WorldTerrainRegistry.require_engine_terrain_key("road")
        self.forest_key = WorldTerrainRegistry.forest_terrain_key()
        self.road = self.registry.entry_for(self.road_key)
        self.forest = self.registry.entry_for(self.forest_key)
        self.custom_key = "steppe"
        self.missing_key = "missing-terrain"
        self.custom = TerrainRegistryEntry(
            system_terrain=self.custom_key,
            terrain_category=self.forest.terrain_category,
            merge_rank=self.road.merge_rank + 1,
        )
        self.registry = WorldTerrainRegistry(self.registry.root + [self.custom])
        self.scale = LightGridScale.from_tile(1000, 32)
        self.ref = LightCellRef(0, 0, 0, 0)
        self.tiles = {(self.ref.gx, self.ref.gy)}
        self.footprint = MaskFootprint(frozenset({self.ref}))

    def paint(self, writer, compose, key, *, preserve_hydro=True):
        ref = self.ref
        if writer is apply_terrain_footprint:
            return writer(compose, self.footprint, system_terrain=key, registry=self.registry,
                          tile_set=self.tiles, preserve_hydro=preserve_hydro)
        if writer is paint_system_terrain:
            return writer(compose, {ref.as_absolute(self.scale.side)}, key, registry=self.registry,
                          tile_set=self.tiles, preserve_hydro=preserve_hydro)
        return writer(compose, ref.gx, ref.gy, ref.tx, ref.ty, key, registry=self.registry,
                      preserve_hydro=preserve_hydro)

    def test_custom_rank_applies_without_engine_key_or_domain_changes(self):
        self.assertEqual(terrain_merge_rank(self.custom_key, self.registry), self.custom.merge_rank)
        self.assertTrue(may_paint_terrain(self.road_key, self.custom_key, self.registry))
        self.assertFalse(may_paint_terrain(self.custom_key, self.road_key, self.registry))

    def test_world_entry_overrides_builtin_canonical_rank(self):
        changed_road = self.road.model_copy(update={"merge_rank": self.forest.merge_rank - 1})
        registry = WorldTerrainRegistry([changed_road, self.forest])
        self.assertEqual(terrain_merge_rank(self.road_key, registry), changed_road.merge_rank)
        self.assertTrue(may_paint_terrain(self.road_key, self.forest_key, registry))
        self.assertFalse(may_paint_terrain(self.forest_key, self.road_key, registry))

    def test_landcover_caller_uses_world_registry_for_custom_policy_key(self):
        world = SimpleNamespace(
            world_uid="world-custom-rank",
            terrain_registry=[self.custom.model_dump(mode="json")],
            terrain_masks={"default_forests": {"system_terrain": self.custom_key}},
        )
        ctx = LightGridBakeContext(
            world=world, locations=[], locations_index=LocationsIndexWire(locations=[]),
            tiles=list(self.tiles), scale=self.scale, terrain_system_keys={self.custom_key},
        )
        compose = LightGridCompose(self.scale)
        ref = self.ref
        cell = compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty)
        cell.system_terrain = self.road_key
        cell.climate_zone_id = ClimateZone.TEMPERATE.world_map_wire_id()
        LandcoverContributor().apply(compose, ctx)
        self.assertEqual(cell.system_terrain, self.custom_key)

    def test_absent_builtin_uses_only_existing_canonical_entry(self):
        registry = WorldTerrainRegistry([self.custom])
        occupancy_key = WorldTerrainRegistry.occupancy_terrain_key()
        canonical_occupancy = WorldTerrainRegistry.canonical_engine().entry_for(occupancy_key)
        self.assertEqual(terrain_merge_rank(self.road_key, registry), self.road.merge_rank)
        self.assertEqual(terrain_merge_rank(occupancy_key, registry), canonical_occupancy.merge_rank)

    def test_missing_key_is_an_error_on_both_sides_and_on_empty_cell(self):
        cases = ((None, self.missing_key), (self.road_key, self.missing_key),
                 (self.missing_key, self.road_key))
        with self.assertRaisesRegex(ValueError, self.missing_key):
            terrain_merge_rank(self.missing_key, self.registry)
        for current, new in cases:
            with self.subTest(current=current, new=new), self.assertRaisesRegex(ValueError, self.missing_key):
                may_paint_terrain(current, new, self.registry)

    def test_empty_cell_is_not_an_invented_zero_rank(self):
        negative = self.custom.model_copy(update={"merge_rank": -self.road.merge_rank})
        registry = WorldTerrainRegistry([negative])
        self.assertTrue(may_paint_terrain(None, self.custom_key, registry))

    def test_equal_rank_keeps_existing_later_writer_semantics(self):
        equal = self.custom.model_copy(update={"merge_rank": self.forest.merge_rank})
        registry = WorldTerrainRegistry([self.forest, equal])
        self.assertTrue(may_paint_terrain(self.custom_key, self.forest_key, registry))
        self.assertTrue(may_paint_terrain(self.forest_key, self.custom_key, registry))

    def test_all_writers_use_custom_rank_and_preserve_hydrology(self):
        writers = (apply_terrain_footprint, paint_system_terrain, paint_system_terrain_cell)
        roles = (WorldMapHydrologyRole.NONE, *PRESERVE_HYDROLOGY_ROLES)
        ref = self.ref
        for writer in writers:
            for role in roles:
                with self.subTest(writer=writer.__name__, role=role):
                    compose = LightGridCompose(self.scale)
                    cell = compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty)
                    cell.system_terrain = self.road_key
                    cell.hydrology_role = role
                    protected = role in PRESERVE_HYDROLOGY_ROLES
                    self.assertEqual(bool(self.paint(writer, compose, self.custom_key)), not protected)
                    expected_key = self.road_key if protected else self.custom_key
                    self.assertEqual(cell.system_terrain, expected_key)
                    self.assertEqual(cell.hydrology_role, role)
                    self.assertTrue(self.paint(writer, compose, self.custom_key, preserve_hydro=False))
                    self.assertEqual(cell.system_terrain, self.custom_key)
                    self.assertFalse(self.paint(writer, compose, self.road_key, preserve_hydro=False))

    def test_writers_reject_missing_key_without_mutating_terrain(self):
        ref = self.ref
        for writer in (apply_terrain_footprint, paint_system_terrain, paint_system_terrain_cell):
            with self.subTest(writer=writer.__name__):
                compose = LightGridCompose(self.scale)
                cell = compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty)
                cell.system_terrain = self.forest_key
                with self.assertRaisesRegex(ValueError, self.missing_key):
                    self.paint(writer, compose, self.missing_key)
                self.assertEqual(cell.system_terrain, self.forest_key)


if __name__ == "__main__":
    unittest.main()
