"""Typed registry operations replace application field/key/rule hardcodes."""

from copy import replace
from itertools import permutations
from pathlib import Path
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.application.jsonValidation.facade import normalize_world
from app.application.worldData.generators.terrain.terrainZ import magma_terrain, subsurface_terrain_at_z
from app.application.worldData.generators.terrain.passes.columnFillPass import run_column_fill
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.pack.read.worldMapPackReader import WorldMapPackReader
from app.dataModel.terrain.enums.terrainFillRole import TerrainFillRole
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain import worldTerrainRegistry as canonical
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverTerrainPolicy
from app.dataModel.worldPack.wire.worldMapCellWire import WorldMapCellWire
from app.db.models.world import World


class TerrainPojoResolutionTests(unittest.TestCase):
    def test_threshold_reuses_canonical_rule_metadata(self):
        template = replace(canonical._FOREST_RAINFALL_RULE, fact="hydrology.water_table",
                           weight=3.5, required=False)
        entry = WorldTerrainRegistry.canonical_defaults().entry_for("forest")
        entry = entry.with_eligibility([template])
        override = LandcoverTerrainPolicy(system_terrain="forest", min_rainfall=60)
        with patch.object(canonical, "_FOREST_RAINFALL_RULE", template):
            result = override.apply_to(entry, source=entry, registry_hills_authored=False)
        self.assertEqual(result.eligibility, [replace(template, lo=60)])
        self.assertEqual(entry.eligibility, [template])
        with self.assertRaises(ValidationError):
            WorldTerrainRegistry.minimum_rainfall_rule(float("nan"))

    def test_typed_hills_priority_omit_and_explicit_null(self):
        entry = WorldTerrainRegistry.canonical_defaults().entry_for("forest")
        for authored_registry, expected in ((False, None), (True, entry.hills)):
            override = LandcoverTerrainPolicy(system_terrain="forest", hills=None)
            self.assertTrue(override.has_authored_hills)
            result = override.apply_to(entry, source=entry, registry_hills_authored=authored_registry)
            self.assertEqual(result.hills, expected)
        omitted = LandcoverTerrainPolicy(system_terrain="forest")
        self.assertFalse(omitted.has_authored_hills)
        self.assertEqual(omitted.apply_to(entry, source=entry, registry_hills_authored=False), entry)

    def test_registry_owned_wire_presence_handles_sparse_author_rows(self):
        raw = [{"system_terrain": "one", "hills": None}, {"system_terrain": "two"},
               {"system_terrain": "three", "hills": {"radius": 8}}]
        self.assertEqual(WorldTerrainRegistry.authored_hill_keys_from_wire(raw), {"one", "three"})

    def test_n_plus_one_fill_roles_priority_and_order_independence(self):
        low = TerrainRegistryEntry(system_terrain="base_fill", terrain_category="solid",
            fill_roles=(TerrainFillRole.SUBSURFACE,), fill_priority=1)
        a = replace(low, system_terrain="custom_a", fill_priority=10)
        b = replace(low, system_terrain="custom_b", fill_priority=10)
        hot = TerrainRegistryEntry(system_terrain="deep_hot", terrain_category="solid",
            fill_roles=(TerrainFillRole.MAGMA,))
        available = {entry.system_terrain for entry in (low, a, b, hot)}
        for entries in permutations((low, a, b, hot)):
            registry = WorldTerrainRegistry(list(entries))
            self.assertEqual(subsurface_terrain_at_z(available, registry=registry), "custom_a")
            self.assertEqual(magma_terrain(available, registry=registry), "deep_hot")
            self.assertEqual(magma_terrain({"custom_b"}, registry=registry), "custom_b")

    def test_missing_role_is_unresolved_and_not_a_first_key_fallback(self):
        registry = WorldTerrainRegistry([TerrainRegistryEntry(system_terrain="arbitrary", terrain_category="solid")])
        with self.assertLogs("app.application.worldData.generators.terrain.terrainZ", "WARNING") as logs:
            with self.assertRaises(ValueError):
                subsurface_terrain_at_z({"arbitrary"}, registry=registry)
        self.assertIn("WarningError", logs.output[0])
        with self.assertRaises(ValidationError):
            TerrainRegistryEntry(system_terrain="invalid", terrain_category="solid", fill_roles=["unknown"])

    def test_custom_fixture_roles_reach_column_fill_and_pack_read(self):
        fixture = Path(__file__).resolve().parents[2] / "fixtures/world_landcover_custom.json"
        data = normalize_world(json.loads(fixture.read_text(encoding="utf-8"))["world"])
        world = World("custom-fill", "Custom", "now", terrain_registry=data["terrain_registry"],
            terrain_masks=data["terrain_masks"], map_subsurface_depth=1, z_min=-2, z_max=20,
            closed_planet_grid=True, magma_band_thickness=1, world_topology_mode="planar")
        heightmap = SurfaceHeightmap(world.world_uid, GridBBox(0, 0, 0, 0), {(0, 0): 3})
        cells = run_column_fill(world, heightmap, {(0, 0): 1}, surface_terrain={(0, 0): "forest"})
        self.assertEqual({cell.z: cell.system_terrain for cell in cells}, {1: "steppe", 2: "steppe", 3: "forest"})
        reader = Mock()
        reader.read_world_map_tile.return_value = (1, [WorldMapCellWire(tx=0, ty=0, surface_z=3,
                                                                      system_terrain="forest")])
        context = SimpleNamespace(reader_for=lambda owner: reader)
        contribution = WorldMapPackReader(context).world_map_contribution(world, 0, 0, 0, 0, 0, 0, 2)
        self.assertEqual(contribution.system_terrain, "steppe")


if __name__ == "__main__":
    unittest.main()
