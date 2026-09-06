"""Farm crops_registry + building template crop_kind."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pydantic import ValidationError

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import crops
from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.flora.worldCropsRegistry import WorldCropsRegistry
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.dataModel.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.dataModel.structure.building.worldBuildingLayoutDefaults import canonical_defaults
from app.db.models.world import World


def _layout(
    system_name: str,
    structure_type: str,
    *,
    crop_kind: CropKind | None = None,
    subjects: list[str] | None = None,
) -> BuildingLayoutTemplate:
    return BuildingLayoutTemplate(
        system_name=system_name,
        structure_type=structure_type,
        display_name=system_name,
        crop_kind=crop_kind,
        subjects=subjects or [],
        levels=[{"z_offset": 0, "rooms": []}],
    )


class CropsRegistryTest(unittest.TestCase):
    def test_canonical_kinds_and_keys(self) -> None:
        reg = WorldCropsRegistry.canonical_defaults()
        self.assertEqual(
            set(CropKind),
            {
                CropKind.GRAIN,
                CropKind.VEGETABLE,
                CropKind.FRUIT,
                CropKind.FIBER,
                CropKind.FODDER,
            },
        )
        self.assertEqual(reg.kind_for("wheat"), CropKind.GRAIN)
        self.assertEqual(reg.kind_for("cabbage"), CropKind.VEGETABLE)
        self.assertEqual(reg.kind_for("apple"), CropKind.FRUIT)
        self.assertEqual(reg.kind_for("flax"), CropKind.FIBER)
        self.assertEqual(reg.kind_for("hay"), CropKind.FODDER)

    def test_runtime_empty_world_merges_canonical(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
        )
        self.assertIn("wheat", crops(world).keys())

    def test_runtime_nonempty_world_does_not_union_canonical(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
            crops_registry=[{
                "system_crop": "barley",
                "crop_kind": "grain",
            }],
        )
        keys = crops(world).keys()
        self.assertIn("barley", keys)
        self.assertNotIn("wheat", keys)

    def test_import_rejects_unknown_crop_kind(self) -> None:
        with self.assertRaises(ImportValidationError) as ctx:
            normalize_world({
                "name": "T",
                "created_at": "2026-01-01T00:00:00",
                "crops_registry": [{
                    "system_crop": "wheat",
                    "crop_kind": "banana",
                }],
            })
        self.assertTrue(
            any("unknown wire value" in err.message for err in ctx.exception.errors),
        )

    def test_outline_rejects_unknown_crop_kind(self) -> None:
        with self.assertRaises(ValidationError):
            BuildingTemplateOutline.model_validate({
                "system_name": "farm_1",
                "structure_type": "farm",
                "display_name": "Farm",
                "crop_kind": "banana",
            })

    def test_builtin_farm_is_grain(self) -> None:
        farm = next(row for row in canonical_defaults() if row.system_name == "farm")
        self.assertEqual(farm.crop_kind, CropKind.GRAIN)

    def test_template_subjects_must_match_kind(self) -> None:
        reg = WorldCropsRegistry.canonical_defaults()
        self.assertEqual(reg.check_template_subjects(CropKind.GRAIN, ["wheat"]), ())
        unknown = reg.check_template_subjects(CropKind.GRAIN, ["not_a_crop"])
        self.assertEqual(unknown, (("not_a_crop", "REF_W_UNKNOWN"),))
        mismatch = reg.check_template_subjects(CropKind.GRAIN, ["flax"])
        self.assertEqual(mismatch, (("flax", "CROP_KIND_MISMATCH"),))
        self.assertEqual(reg.check_template_subjects(None, ["wheat"]), ())

    def test_prefer_subjects_uses_crop_kind(self) -> None:
        generic = _layout("farm", "farm", crop_kind=CropKind.GRAIN)
        orchard = _layout("orchard_1", "farm", crop_kind=CropKind.FRUIT)
        wheat = _layout("wheat_farm_1", "farm", subjects=["wheat"])
        tagged = BuildingCatalog.prefer_subjects(
            (generic, orchard, wheat), ["wheat"], crop_kinds={CropKind.GRAIN},
        )
        self.assertEqual([row.system_name for row in tagged], ["wheat_farm_1"])
        by_kind = BuildingCatalog.prefer_subjects(
            (generic, orchard), ["wheat"], crop_kinds={CropKind.GRAIN},
        )
        self.assertEqual([row.system_name for row in by_kind], ["farm"])


class FarmTemplateImportTest(unittest.IsolatedAsyncioTestCase):
    async def test_import_rejects_farm_subject_wrong_kind(self) -> None:
        world = World(
            world_uid="w1",
            name="T",
            created_at="2026-01-01T00:00:00",
        )
        worlds = MagicMock()
        worlds.get_by_id = AsyncMock(return_value=world)
        service = BuildingTemplateLibraryService(repo=MagicMock(), world_service=worlds)
        result = await service.import_bodies_into_world("w1", [{
            "system_name": "confused_farm",
            "structure_type": "farm",
            "display_name": "Farm",
            "crop_kind": "grain",
            "subjects": ["flax"],
        }])
        self.assertEqual(result.failed, 1)
        self.assertIn("CROP_KIND_MISMATCH", result.errors[0].message)


if __name__ == "__main__":
    unittest.main()
