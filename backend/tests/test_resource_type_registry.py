"""Extract resource_type_registry + building template resource_kind."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pydantic import ValidationError

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import resource_types
from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.resources.worldResourceTypeRegistry import WorldResourceTypeRegistry
from app.dataModel.locations.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.dataModel.locations.structure.building.worldBuildingLayoutDefaults import canonical_defaults
from app.db.models.world import World


def _layout(
    system_name: str,
    structure_type: str,
    *,
    resource_kind: ResourceKind | None = None,
    subjects: list[str] | None = None,
) -> PlotLayoutTemplate:
    del structure_type
    return PlotLayoutTemplate(
        system_name=system_name,
        display_name=system_name,
        resource_kind=resource_kind,
        subjects=subjects or [],
        main_building={"structure": "00000000-0000-4000-8000-000000000004"},
    )


class ResourceRegistryTest(unittest.TestCase):
    def test_canonical_kinds_and_keys(self) -> None:
        reg = WorldResourceTypeRegistry.canonical_defaults()
        self.assertEqual(
            set(ResourceKind),
            {ResourceKind.ORE, ResourceKind.STONE, ResourceKind.TIMBER, ResourceKind.LIQUID},
        )
        self.assertEqual(reg.kind_for("iron_ore"), ResourceKind.ORE)
        self.assertEqual(reg.kind_for("copper_ore"), ResourceKind.ORE)
        self.assertEqual(reg.kind_for("timber"), ResourceKind.TIMBER)
        self.assertIsNone(reg.kind_for("iron"))

    def test_runtime_empty_world_merges_canonical(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
        )
        self.assertIn("iron_ore", resource_types(world).keys())

    def test_runtime_nonempty_world_does_not_union_canonical(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
            resource_type_registry=[{
                "system_resource": "mithril_ore",
                "resource_kind": "ore",
            }],
        )
        keys = resource_types(world).keys()
        self.assertIn("mithril_ore", keys)
        self.assertNotIn("iron_ore", keys)

    def test_import_rejects_unknown_resource_kind(self) -> None:
        with self.assertRaises(ImportValidationError) as ctx:
            normalize_world({
                "name": "T",
                "created_at": "2026-01-01T00:00:00",
                "resource_type_registry": [{
                    "system_resource": "iron_ore",
                    "resource_kind": "banana",
                }],
            })
        self.assertTrue(
            any("unknown wire value" in err.message for err in ctx.exception.errors),
        )

    def test_outline_rejects_unknown_resource_kind(self) -> None:
        with self.assertRaises(ValidationError):
            BuildingTemplateOutline.model_validate({
                "system_name": "mine_1",
                "structure_type": "mine",
                "display_name": "Mine",
                "resource_kind": "banana",
            })

    def test_builtin_mine_is_ore(self) -> None:
        mine = next(row for row in canonical_defaults() if row.system_name == "mine")
        self.assertEqual(mine.resource_kind, ResourceKind.ORE)

    def test_template_subjects_must_match_kind(self) -> None:
        reg = WorldResourceTypeRegistry.canonical_defaults()
        self.assertEqual(
            reg.check_template_subjects(ResourceKind.ORE, ["iron_ore"]),
            (),
        )
        unknown = reg.check_template_subjects(ResourceKind.ORE, ["not_a_resource"])
        self.assertEqual(unknown, (("not_a_resource", "REF_W_UNKNOWN"),))
        mismatch = reg.check_template_subjects(ResourceKind.ORE, ["timber"])
        self.assertEqual(mismatch, (("timber", "RESOURCE_KIND_MISMATCH"),))
        self.assertEqual(reg.check_template_subjects(None, ["iron_ore"]), ())

    def test_prefer_subjects_uses_resource_kind(self) -> None:
        generic = _layout("mine", "mine", resource_kind=ResourceKind.ORE)
        timber = _layout("lumber_camp", "mine", resource_kind=ResourceKind.TIMBER)
        iron = _layout("iron_mine_1", "mine", subjects=["iron_ore"])
        pool = (generic, timber, iron)
        tagged = BuildingCatalog.prefer_subjects(
            pool, ["iron_ore"], {ResourceKind.ORE},
        )
        self.assertEqual([row.system_name for row in tagged], ["iron_mine_1"])
        by_kind = BuildingCatalog.prefer_subjects(
            (generic, timber), ["iron_ore"], {ResourceKind.ORE},
        )
        self.assertEqual([row.system_name for row in by_kind], ["mine"])


class BuildingTemplateImportTest(unittest.IsolatedAsyncioTestCase):
    async def test_import_rejects_extract_subject_not_in_registry(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
        )
        worlds = MagicMock()
        worlds.get_by_id = AsyncMock(return_value=world)
        service = BuildingTemplateLibraryService(
            repo=MagicMock(), world_service=worlds,
            catalog=PackCatalogRepos(packs=AsyncMock(), members=AsyncMock()),
        )
        result = await service.import_bodies_into_world("w1", [{
            "system_name": "confused_mine",
            "structure_type": "mine",
            "display_name": "Mine",
            "resource_kind": "ore",
            "subjects": ["timber"],
        }])
        self.assertEqual(result.failed, 1)
        self.assertIn("RESOURCE_KIND_MISMATCH", result.errors[0].message)


if __name__ == "__main__":
    unittest.main()
