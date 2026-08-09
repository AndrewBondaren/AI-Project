"""Unit: corrupt world climate defaults → import normalize repair (not synthetic water)."""

from __future__ import annotations

import asyncio
import unittest

from app.application.worldData.generators.climate.precipitation import (
    resolve_world_precipitation_liquid,
)
from app.application.worldData.repairWorldDefaults import (
    WorldClimateDefaultsError,
    apply_import_normalize_to_world,
    ensure_world_climate_defaults,
    precipitation_liquid_resolvable,
    world_climate_defaults_need_repair,
)
from app.db.models.world import World


def _bare_world(**kwargs) -> World:
    data = {
        "world_uid": "w-repair",
        "name": "Repair",
        "created_at": "2026-01-01T00:00:00Z",
        "material_registry": [],
        "precipitation_liquid": None,
    }
    data.update(kwargs)
    return World(**data)


class RepairWorldDefaultsTest(unittest.TestCase):
    def test_empty_registry_needs_row_repair(self) -> None:
        world = _bare_world()
        self.assertTrue(world_climate_defaults_need_repair(world))

    def test_solids_only_registry_needs_repair(self) -> None:
        world = _bare_world(
            material_registry=[{
                "system_material": "stone",
                "display_name": "Stone",
                "material_category": "solid",
            }],
            precipitation_liquid="water",
        )
        self.assertTrue(world_climate_defaults_need_repair(world))
        with self.assertRaises(WorldClimateDefaultsError):
            resolve_world_precipitation_liquid(world)

    def test_normalize_repairs_empty_row(self) -> None:
        world = _bare_world()
        changed = apply_import_normalize_to_world(world)
        self.assertTrue(changed)
        self.assertFalse(world_climate_defaults_need_repair(world))
        self.assertTrue(precipitation_liquid_resolvable(world))
        liquid = resolve_world_precipitation_liquid(world)
        self.assertEqual(liquid.system_material, "water")
        self.assertTrue(liquid.material_category.is_liquid())
        self.assertTrue(isinstance(world.material_registry, list))
        self.assertGreater(len(world.material_registry), 0)

    def test_ensure_async_without_repo(self) -> None:
        world = _bare_world(world_uid="w-ensure")
        repaired = asyncio.run(ensure_world_climate_defaults(world, repo=None))
        self.assertTrue(precipitation_liquid_resolvable(repaired))
        self.assertEqual(
            resolve_world_precipitation_liquid(repaired).system_material,
            "water",
        )


if __name__ == "__main__":
    unittest.main()
