"""StructureTemplate §3.4b — level/room purpose aggregation + uuid identity."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.buildingPurpose import BuildingPurpose
from tests.structureWire import room_wire, level_wire

_UID = "00000000-0000-4000-8000-0000000000aa"


def _structure(**kwargs) -> StructureTemplate:
    if "levels" in kwargs:
        kwargs["levels"] = [level_wire(**(level | {
            "rooms": [room_wire(**room) for room in level["rooms"]],
        })) for level in kwargs["levels"]]
    return StructureTemplate.model_validate({
        "system_name": _UID,
        "display_name": "Test",
        **kwargs,
    })


class PurposeAggregationTest(unittest.TestCase):
    def test_omit_structure_types_derives_from_rooms(self) -> None:
        tpl = _structure(
            levels=[
                {
                    "z_offset": 0,
                    "purpose": "tavern",
                    "rooms": [{"room_id": "hall"}, {"room_id": "kitchen"}],
                },
                {
                    "z_offset": 1,
                    "purpose": "house",
                    "rooms": [{"room_id": "bed"}],
                },
            ],
        )
        self.assertEqual(
            tpl.structure_types,
            [BuildingPurpose.TAVERN, BuildingPurpose.HOUSE],
        )
        self.assertEqual(
            tpl.room_purposes(),
            {
                "hall": BuildingPurpose.TAVERN,
                "kitchen": BuildingPurpose.TAVERN,
                "bed": BuildingPurpose.HOUSE,
            },
        )

    def test_explicit_superset_of_derived_ok(self) -> None:
        tpl = _structure(
            structure_types=["tavern", "inn"],
            levels=[{
                "z_offset": 0,
                "purpose": "tavern",
                "rooms": [{"room_id": "hall"}],
            }],
        )
        self.assertEqual(
            tpl.structure_types,
            [BuildingPurpose.TAVERN, BuildingPurpose.INN],
        )

    def test_derived_not_subset_of_explicit_fails(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            _structure(
                structure_types=["tavern"],
                levels=[{
                    "z_offset": 0,
                    "rooms": [{"room_id": "bed", "purpose": "house"}],
                }],
            )
        self.assertIn("bed", str(ctx.exception))

    def test_family_purpose_on_level_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _structure(
                levels=[{
                    "z_offset": 0,
                    "purpose": "trade",
                    "rooms": [{"room_id": "hall"}],
                }],
            )

    def test_family_purpose_on_room_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _structure(
                levels=[{
                    "z_offset": 0,
                    "rooms": [{"room_id": "hall", "purpose": "culture"}],
                }],
            )

    def test_unknown_purpose_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _structure(
                levels=[{
                    "z_offset": 0,
                    "rooms": [{"room_id": "hall", "purpose": "not_a_leaf"}],
                }],
            )

    def test_explicit_null_room_is_service(self) -> None:
        tpl = _structure(
            levels=[{
                "z_offset": 0,
                "purpose": "tavern",
                "rooms": [
                    {"room_id": "hall"},
                    {"room_id": "storage", "purpose": None},
                ],
            }],
        )
        self.assertNotIn("storage", tpl.room_purposes())
        self.assertEqual(tpl.room_purposes()["hall"], BuildingPurpose.TAVERN)

    def test_no_purposes_derives_house(self) -> None:
        tpl = _structure(
            levels=[{
                "z_offset": 0,
                "rooms": [{"room_id": "hall"}],
            }],
        )
        self.assertEqual(tpl.room_purposes(), {})
        self.assertEqual(tpl.structure_types, [BuildingPurpose.HOUSE])

    def test_empty_explicit_list_derives(self) -> None:
        tpl = _structure(
            structure_types=[],
            levels=[{
                "z_offset": 0,
                "purpose": "tavern",
                "rooms": [{"room_id": "hall"}],
            }],
        )
        self.assertEqual(tpl.structure_types, [BuildingPurpose.TAVERN])

    def test_legacy_structure_type_alias_is_explicit(self) -> None:
        tpl = _structure(
            structure_type="tavern",
            levels=[{
                "z_offset": 0,
                "purpose": "tavern",
                "rooms": [{"room_id": "hall"}],
            }],
        )
        self.assertEqual(tpl.structure_types, [BuildingPurpose.TAVERN])


class StructureCatalogDuplicateTest(unittest.TestCase):
    def test_duplicate_system_name_rejected(self) -> None:
        first = _structure(display_name="Alpha")
        second = _structure(display_name="Beta")
        with self.assertRaises(ValueError) as ctx:
            StructureCatalog([first, second])
        message = str(ctx.exception)
        self.assertIn(_UID, message)
        self.assertIn("Alpha", message)
        self.assertIn("Beta", message)


if __name__ == "__main__":
    unittest.main()
