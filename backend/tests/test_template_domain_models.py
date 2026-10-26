"""A1 contracts — tz_domain_template_libraries.md §1–2/5."""

import json
from pathlib import Path
import unittest
from dataclasses import FrozenInstanceError

from pydantic import ValidationError

from app.application.templateLibrary.templateContracts import (
    ReliefTemplateSnapshot, TemplateEntry, WorldTemplateSnapshot,
)
from app.dataModel.cascade.cascadeVerify import verify_cascade_contract
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.structure.building import (
    BuildingBodyTemplate, BuildingTemplate, PlotLayoutTemplate, PlotTemplate,
    StructureTemplate,
)

_PACK = "00000000-0000-4000-8000-000000000001"
_FIRST = "00000000-0000-4000-8000-000000000011"
_SECOND = "00000000-0000-4000-8000-000000000012"
_STRUCTURE = "00000000-0000-4000-8000-000000000013"


def building(**overrides):
    return BuildingTemplate.model_validate({
        "system_name": "town_hall", "display_name": "Town hall",
        "structure": _STRUCTURE, **overrides,
    })


def plot(**overrides):
    return PlotTemplate.model_validate({
        "system_name": "town_hall_plot", "display_name": "Town hall plot", **overrides,
    })


class DomainModelsTest(unittest.TestCase):
    def test_building_reuses_parameter_defaults_without_member_identity_in_body(self):
        body = building()
        inline = BuildingBodyTemplate(structure=_STRUCTURE)
        for name in BuildingBodyTemplate.model_fields:
            self.assertEqual(getattr(body, name), getattr(inline, name))
        self.assertNotIn("template_uid", body.model_dump())

    def test_valid_overrides_and_explicit_zero_false_null_are_preserved(self):
        body = building(foundation_depth=0, porch_has_roof=False,
                        roof_material=None, foundation_type="none", roof_type="flat")
        self.assertEqual(body.foundation_depth, 0)
        self.assertFalse(body.porch_has_roof)
        self.assertIsNone(body.roof_material)
        self.assertEqual(body.foundation_type, "none")
        self.assertEqual(body.roof_type, "flat")
        self.assertIn("foundation_depth", body.model_fields_set)

    def test_invalid_override_is_not_replaced_with_default(self):
        for overrides in ({"foundation_depth": -1}, {"foundation_depth": None},
                          {"roof_type": None}, {"structure": None}):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                building(**overrides)

    def test_library_building_requires_names_and_structure(self):
        raw = building().model_dump()
        for name in ("structure", "system_name", "display_name"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                BuildingTemplate.model_validate({k: v for k, v in raw.items() if k != name})

    def test_inline_building_does_not_require_library_member_metadata(self):
        body = plot(main_building={"structure": _STRUCTURE})
        self.assertIsInstance(body.main_building, BuildingBodyTemplate)
        self.assertNotIn("system_name", body.main_building.model_dump())

    def test_plot_preserves_main_and_secondary_building_parameters(self):
        body = plot(main_building={"structure": _STRUCTURE, "foundation_depth": 0},
                    secondary_buildings=[{"structure": _STRUCTURE, "porch_has_roof": True}])
        restored = PlotTemplate.model_validate_json(body.model_dump_json())
        self.assertEqual(restored, body)
        self.assertEqual(restored.main_building.foundation_depth, 0)
        self.assertTrue(restored.secondary_buildings[0].porch_has_roof)

    def test_plot_without_building_does_not_materialize_default_building(self):
        for overrides in ({}, {"main_building": None, "secondary_buildings": []}):
            body = plot(**overrides)
            self.assertIsNone(body.main_building)
            self.assertEqual(body.secondary_buildings, [])
            self.assertIsNone(body.economic_tier)
            self.assertIsNone(body.economic_tier_band)
            self.assertIsNone(body.economic_tier_range)

    def test_plot_does_not_duplicate_registered_cascade_channels(self):
        self.assertIs(PlotTemplate, PlotLayoutTemplate)
        verify_cascade_contract(LocationContext)

    def test_existing_plot_fixtures_remain_valid(self):
        paths = list((Path(__file__).resolve().parents[2] / "fixtures" / "templates").glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(PlotTemplate.model_validate(raw), PlotLayoutTemplate.model_validate(raw))


class TemplateSnapshotTest(unittest.TestCase):
    def test_uid_identity_preserves_same_name_members_and_sorted_candidates(self):
        entries = {uid: TemplateEntry(uid, _PACK, plot()) for uid in (_SECOND, _FIRST)}
        snapshot = WorldTemplateSnapshot("world", plots=entries)
        self.assertEqual(tuple(snapshot.plots), (_FIRST, _SECOND))
        self.assertEqual(len(snapshot.plots), 2)
        self.assertEqual(snapshot.plots[_FIRST].body.system_name,
                         snapshot.plots[_SECOND].body.system_name)

    def test_snapshot_copies_and_protects_uid_indexes(self):
        entries = {_FIRST: TemplateEntry(_FIRST, _PACK, plot())}
        snapshot = WorldTemplateSnapshot("world", plots=entries)
        entries.clear()
        self.assertIn(_FIRST, snapshot.plots)
        with self.assertRaises(TypeError):
            snapshot.plots[_SECOND] = snapshot.plots[_FIRST]
        with self.assertRaises(FrozenInstanceError):
            snapshot.world_uid = "other"

    def test_entry_rejects_names_in_place_of_template_or_pack_uid(self):
        for uid, owner in (("town_hall", _PACK), (_FIRST, "base")):
            with self.subTest(uid=uid, owner=owner), self.assertRaises(ValueError):
                TemplateEntry(uid, owner, plot())

    def test_snapshot_rejects_inconsistent_index_and_wrong_domain_body(self):
        entry = TemplateEntry(_FIRST, _PACK, plot())
        with self.assertRaises(ValueError):
            WorldTemplateSnapshot("world", plots={_SECOND: entry})
        with self.assertRaises(TypeError):
            WorldTemplateSnapshot("world", buildings={_FIRST: entry})

    def test_structure_model_a_identity_is_checked(self):
        body = StructureTemplate(system_name=_STRUCTURE, display_name="Geometry")
        entry = TemplateEntry(_STRUCTURE, _PACK, body)
        snapshot = WorldTemplateSnapshot("world", structures={_STRUCTURE: entry})
        self.assertIs(snapshot.structures[_STRUCTURE].body, body)
        wrong = TemplateEntry(_FIRST, _PACK, body)
        with self.assertRaises(ValueError):
            WorldTemplateSnapshot("world", structures={_FIRST: wrong})

    def test_same_uid_cannot_identify_members_in_two_domains(self):
        with self.assertRaises(ValueError):
            WorldTemplateSnapshot("world", plots={_FIRST: TemplateEntry(_FIRST, _PACK, plot())},
                                  buildings={_FIRST: TemplateEntry(_FIRST, _PACK, building())})

    def test_relief_snapshot_is_separate_and_rejects_other_domain_bodies(self):
        self.assertEqual(dict(ReliefTemplateSnapshot("world").templates), {})
        with self.assertRaises(TypeError):
            ReliefTemplateSnapshot("world", {_FIRST: TemplateEntry(_FIRST, _PACK, plot())})


if __name__ == "__main__":
    unittest.main()
