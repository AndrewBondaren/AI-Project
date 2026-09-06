"""Livestock livestock_registry + building template livestock_kind."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pydantic import ValidationError

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import livestock
from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.livestock.worldLivestockRegistry import WorldLivestockRegistry
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.dataModel.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.dataModel.structure.building.worldBuildingLayoutDefaults import canonical_defaults
from app.db.models.world import World


def _layout(
    system_name: str,
    structure_type: str,
    *,
    livestock_kind: LivestockKind | None = None,
    subjects: list[str] | None = None,
) -> BuildingLayoutTemplate:
    return BuildingLayoutTemplate(
        system_name=system_name,
        structure_type=structure_type,
        display_name=system_name,
        livestock_kind=livestock_kind,
        subjects=subjects or [],
        levels=[{"z_offset": 0, "rooms": []}],
    )


class LivestockRegistryTest(unittest.TestCase):
    def test_canonical_kinds_and_keys(self) -> None:
        reg = WorldLivestockRegistry.canonical_defaults()
        self.assertEqual(
            set(LivestockKind),
            {
                LivestockKind.MEAT,
                LivestockKind.DAIRY,
                LivestockKind.FIBER,
                LivestockKind.DRAFT,
                LivestockKind.MOUNT,
            },
        )
        self.assertEqual(reg.kind_for("pig"), LivestockKind.MEAT)
        self.assertEqual(reg.kind_for("chicken"), LivestockKind.MEAT)
        self.assertEqual(reg.kind_for("cow"), LivestockKind.DAIRY)
        self.assertEqual(reg.kind_for("sheep"), LivestockKind.FIBER)
        self.assertEqual(reg.kind_for("ox"), LivestockKind.DRAFT)
        self.assertEqual(reg.kind_for("donkey"), LivestockKind.DRAFT)
        self.assertEqual(reg.kind_for("horse"), LivestockKind.MOUNT)

    def test_runtime_empty_world_merges_canonical(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
        )
        self.assertIn("cow", livestock(world).keys())

    def test_runtime_nonempty_world_does_not_union_canonical(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
            livestock_registry=[{
                "system_livestock": "yak",
                "livestock_kind": "dairy",
            }],
        )
        keys = livestock(world).keys()
        self.assertIn("yak", keys)
        self.assertNotIn("cow", keys)

    def test_import_rejects_unknown_livestock_kind(self) -> None:
        with self.assertRaises(ImportValidationError) as ctx:
            normalize_world({
                "name": "T",
                "created_at": "2026-01-01T00:00:00",
                "livestock_registry": [{
                    "system_livestock": "cow",
                    "livestock_kind": "egg",
                }],
            })
        self.assertTrue(
            any("unknown wire value" in err.message for err in ctx.exception.errors),
        )

    def test_outline_rejects_unknown_livestock_kind(self) -> None:
        with self.assertRaises(ValidationError):
            BuildingTemplateOutline.model_validate({
                "system_name": "pen_1",
                "structure_type": "livestock",
                "display_name": "Pen",
                "livestock_kind": "egg",
            })

    def test_builtin_livestock_has_no_kind(self) -> None:
        row = next(row for row in canonical_defaults() if row.system_name == "livestock")
        self.assertIsNone(row.livestock_kind)

    def test_template_subjects_must_match_kind(self) -> None:
        reg = WorldLivestockRegistry.canonical_defaults()
        self.assertEqual(reg.check_template_subjects(LivestockKind.DAIRY, ["cow"]), ())
        unknown = reg.check_template_subjects(LivestockKind.DAIRY, ["not_an_animal"])
        self.assertEqual(unknown, (("not_an_animal", "REF_W_UNKNOWN"),))
        mismatch = reg.check_template_subjects(LivestockKind.DAIRY, ["horse"])
        self.assertEqual(mismatch, (("horse", "LIVESTOCK_KIND_MISMATCH"),))
        self.assertEqual(reg.check_template_subjects(None, ["cow"]), ())

    def test_prefer_subjects_uses_livestock_kind(self) -> None:
        generic = _layout("livestock", "livestock")
        dairy = _layout("dairy_pen", "livestock", livestock_kind=LivestockKind.DAIRY)
        cow = _layout("cow_pen_1", "livestock", subjects=["cow"])
        tagged = BuildingCatalog.prefer_subjects(
            (generic, dairy, cow), ["cow"], livestock_kinds={LivestockKind.DAIRY},
        )
        self.assertEqual([row.system_name for row in tagged], ["cow_pen_1"])
        by_kind = BuildingCatalog.prefer_subjects(
            (generic, dairy), ["cow"], livestock_kinds={LivestockKind.DAIRY},
        )
        self.assertEqual([row.system_name for row in by_kind], ["dairy_pen"])
        untagged = BuildingCatalog.prefer_subjects(
            (generic, dairy), ["cow"], livestock_kinds={LivestockKind.MOUNT},
        )
        self.assertEqual([row.system_name for row in untagged], ["livestock"])


class LivestockTemplateImportTest(unittest.IsolatedAsyncioTestCase):
    async def test_import_rejects_livestock_subject_wrong_kind(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
        )
        worlds = MagicMock()
        worlds.get_by_id = AsyncMock(return_value=world)
        service = BuildingTemplateLibraryService(repo=MagicMock(), world_service=worlds)
        result = await service.import_bodies_into_world("w1", [{
            "system_name": "confused_pen",
            "structure_type": "livestock",
            "display_name": "Pen",
            "livestock_kind": "dairy",
            "subjects": ["horse"],
        }])
        self.assertEqual(result.failed, 1)
        self.assertIn("LIVESTOCK_KIND_MISMATCH", result.errors[0].message)


if __name__ == "__main__":
    unittest.main()
