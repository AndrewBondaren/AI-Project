"""Unit: RELIEF-T-28/T-29 worldRow runtime resolve + canonical merge via WORLD_SLICES."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.application.jsonValidation.worldRow import (
    barrier_templates,
    climate_zones,
    district_templates,
    hydrology,
    lore,
    materials,
    relief_pick_policy,
    relief_template_registry,
    terrain,
)
from app.application.jsonValidation.worldSlices import (
    WORLD_SLICE_BY_POJO,
    slice_column_key,
    slice_for_pojo,
)
from app.dataModel import WorldHydrology, WorldMaterialRegistry, WorldTerrainRegistry
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    WorldDistrictTemplateRegistry,
)
from app.dataModel.structure.barrier.worldBarrierTemplateRegistry import (
    WorldBarrierTemplateRegistry,
)
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy
from app.dataModel.terrain.relief.worldReliefTemplateRegistry import (
    WorldReliefTemplateRegistry,
)


class WorldRowSliceResolveTest(unittest.TestCase):
    def test_slice_column_key_matches_pojo(self) -> None:
        self.assertEqual(
            slice_column_key(WorldReliefTemplateRegistry),
            "relief_template_registry",
        )
        self.assertEqual(slice_column_key(WorldTerrainRegistry), "terrain_registry")
        self.assertIn(WorldMaterialRegistry, WORLD_SLICE_BY_POJO)

    def test_empty_world_uses_defaults(self) -> None:
        world = SimpleNamespace(world_uid="w1")
        self.assertEqual(list(terrain(world).root), list(
            WorldTerrainRegistry.canonical_defaults().root,
        ))
        self.assertEqual(list(materials(world).root), list(
            WorldMaterialRegistry.canonical_defaults().root,
        ))
        self.assertEqual(
            hydrology(world).model_dump(mode="json"),
            WorldHydrology.canonical_empty().model_dump(mode="json"),
        )
        self.assertEqual(
            relief_pick_policy(world).model_dump(mode="json"),
            WorldReliefPickPolicy.canonical_defaults().model_dump(mode="json"),
        )
        self.assertEqual(list(relief_template_registry(world).root), [])

    def test_registry_list_reads_slice_column(self) -> None:
        world = SimpleNamespace(
            world_uid="w1",
            relief_template_registry=[{
                "system_template_uid": "t1",
                "system_name": "t1",
                "display_name": "T1",
                "context": "road_shoulder",
            }],
        )
        reg = relief_template_registry(world)
        self.assertEqual(len(reg.root), 1)
        self.assertEqual(reg.root[0].system_template_uid, "t1")

    def test_climate_zones_wire_adapter_empty(self) -> None:
        world = SimpleNamespace(world_uid="w1", climate_zone_registry=None)
        zones = climate_zones(world)
        self.assertTrue(len(zones.root) > 0)

    def test_lore_dict_empty_uses_canonical(self) -> None:
        world = SimpleNamespace(world_uid="w1")
        self.assertTrue(len(lore(world).root) > 0)


class WorldRowRuntimeMergeT29Test(unittest.TestCase):
    def test_slice_reads_pojo_merge_id(self) -> None:
        district_slice = slice_for_pojo(WorldDistrictTemplateRegistry)
        barrier_slice = slice_for_pojo(WorldBarrierTemplateRegistry)
        assert district_slice is not None and barrier_slice is not None
        self.assertEqual(district_slice.runtime_merge_id_field, "system_name")
        self.assertEqual(barrier_slice.runtime_merge_id_field, "system_type")
        terrain_slice = slice_for_pojo(WorldTerrainRegistry)
        assert terrain_slice is not None
        self.assertIsNone(terrain_slice.runtime_merge_id_field)

    def test_district_empty_is_canonical(self) -> None:
        world = SimpleNamespace(world_uid="w1")
        got = district_templates(world)
        canon = WorldDistrictTemplateRegistry.canonical_defaults()
        self.assertEqual(len(got.root), len(canon.root))
        self.assertEqual(
            {e.system_name for e in got.root},
            {e.system_name for e in canon.root},
        )

    def test_district_world_override_merges(self) -> None:
        world = SimpleNamespace(
            world_uid="w1",
            district_template_registry=[{
                "system_name": "civic_center",
                "display_name": "Override Civic",
                "district_type": "civic",
            }],
        )
        got = district_templates(world)
        canon_n = len(WorldDistrictTemplateRegistry.canonical_defaults().root)
        self.assertEqual(len(got.root), canon_n)
        civic = next(e for e in got.root if e.system_name == "civic_center")
        self.assertEqual(civic.display_name, "Override Civic")

    def test_barrier_world_override_merges(self) -> None:
        world = SimpleNamespace(
            world_uid="w1",
            barrier_template_registry=[{
                "system_type": "wooden_fence",
                "glossary_ref": "barrier_wooden_fence",
                "wall_material": {"pick_from": ["wood"]},
                "height_levels": {"min": 1, "max": 1},
                "gates": {"min": 9, "max": 9},
            }],
        )
        got = barrier_templates(world)
        canon_n = len(WorldBarrierTemplateRegistry.canonical_defaults().root)
        self.assertEqual(len(got.root), canon_n)
        wooden = next(e for e in got.root if e.system_type == "wooden_fence")
        self.assertEqual(wooden.gates.min, 9)


if __name__ == "__main__":
    unittest.main()
