"""Plot drawing: envelope + main_building.structure ref into the global library."""

from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path

from pydantic import ValidationError

from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import (
    BuildingLayoutCache,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.application.worldData.structureTemplateFsImport import load_structure_stdlib
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
    plot_has_building,
    structure_ref_of,
)
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.buildingPurpose import (
    BuildingPurpose,
    BuildingPurposeFamily,
)
from app.db.models.world import World

_REPO = Path(__file__).resolve().parents[2]
_TEMPLATES = _REPO / "fixtures" / "templates"
_STRUCTURES = _REPO / "structures_templates"


def _stdlib() -> StructureCatalog:
    return StructureCatalog(load_structure_stdlib(_STRUCTURES))

TAVERN_1_UID = "5a1f2b3c-4d5e-4f6a-8b7c-9d0e1f2a3b4c"


def _world() -> World:
    return World(
        world_uid="w-plot",
        name="plot",
        created_at="2026-01-01T00:00:00",
    )


def _plot(
    system_name: str,
    purpose: str,
    **fields,
) -> tuple[PlotLayoutTemplate, StructureTemplate]:
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"test-structure|{system_name}"))
    plot = PlotLayoutTemplate(
        system_name=system_name,
        display_name=system_name,
        main_building={"structure": uid},
        **fields,
    )
    structure = StructureTemplate(
        system_name=uid,
        display_name=system_name,
        structure_types=[purpose],
        levels=[{"z_offset": 0, "rooms": []}],
    )
    return plot, structure


def _catalog(*pairs: tuple[PlotLayoutTemplate, StructureTemplate]):
    from app.dataModel.locations.structure.building.buildingCatalog import BuildingCatalog

    return BuildingCatalog.from_layouts(
        [plot for plot, _s in pairs],
        StructureCatalog([s for _p, s in pairs]),
    )


class PlotLayoutContractTest(unittest.TestCase):
    def test_inn_small_references_shared_tavern_structure(self) -> None:
        plot = PlotLayoutTemplate.model_validate(
            json.loads((_TEMPLATES / "inn_small.json").read_text(encoding="utf-8"))
        )
        self.assertEqual(plot.system_name, "inn_small")
        self.assertEqual(plot.plot_type, BuildingPurposeFamily.TRADE)
        self.assertIsNotNone(plot.occupied_footprint)
        self.assertEqual(plot.occupied_footprint.width, 16)
        self.assertEqual(plot.occupied_footprint.depth, 16)
        self.assertTrue(plot_has_building(plot))
        self.assertIsNotNone(plot.main_building)
        self.assertEqual(str(structure_ref_of(plot)), TAVERN_1_UID)

    def test_plot_rejects_legacy_root_levels(self) -> None:
        with self.assertRaises(ValidationError):
            PlotLayoutTemplate.model_validate({
                "system_name": "legacy",
                "display_name": "Legacy",
                "levels": [{"z_offset": 0, "rooms": []}],
            })

    def test_plot_rejects_legacy_body_key(self) -> None:
        with self.assertRaises(ValidationError):
            PlotLayoutTemplate.model_validate({
                "system_name": "legacy",
                "display_name": "Legacy",
                "structure_types": ["tavern"],
                "building": {"system_name": "x"},
            })

    def test_structure_rejects_semantic_name(self) -> None:
        with self.assertRaises(ValidationError):
            StructureTemplate.model_validate({
                "system_name": "inn_small",
                "display_name": "Tavern",
            })

    def test_structure_accepts_uuid_and_normalizes_lower(self) -> None:
        template = StructureTemplate.model_validate({
            "system_name": "5A1F2B3C-4D5E-4F6A-8B7C-9D0E1F2A3B4C",
            "display_name": "Tavern",
        })
        self.assertEqual(str(template.system_name), TAVERN_1_UID)

    def test_plaza_plot_has_no_building(self) -> None:
        plaza = PlotLayoutTemplate(
            system_name="plaza_1",
            display_name="Площадь",
            plot_type=BuildingPurposeFamily.PUBLIC,
        )
        self.assertFalse(plot_has_building(plaza))
        self.assertIsNone(structure_ref_of(plaza))

    def test_leaves_of_plaza_rule_and_resolve(self) -> None:
        plot, structure = _plot("tavern_plot", "tavern")
        catalog = StructureCatalog([structure])
        self.assertEqual(catalog.leaves_of(plot), (BuildingPurpose.TAVERN,))
        plaza = PlotLayoutTemplate(
            system_name="plaza_1",
            display_name="Площадь",
            plot_type=BuildingPurposeFamily.PUBLIC,
        )
        self.assertEqual(catalog.leaves_of(plaza), (BuildingPurpose.PLAZA,))
        yard = PlotLayoutTemplate(
            system_name="yard_1",
            display_name="Двор",
            plot_type=BuildingPurposeFamily.DWELLING,
        )
        self.assertEqual(catalog.leaves_of(yard), ())
        self.assertEqual(StructureCatalog.empty().leaves_of(plot), ())

    def test_catalog_of_structure_type_via_structure_ref(self) -> None:
        catalog = _catalog(
            _plot("inn_small", "tavern"),
            _plot("town_hall", "town_hall"),
        )
        self.assertEqual(
            [row.system_name for row in catalog.of_structure_type("tavern")],
            ["inn_small"],
        )

    def test_canonical_defaults_resolve_in_stdlib(self) -> None:
        catalog = assemble_building_catalog(_world(), structures=_stdlib())
        inn = catalog.by_system_name("inn_small")
        self.assertIsNotNone(inn)
        self.assertTrue(plot_has_building(inn))
        stdlib_uids = {str(t.system_name) for t in load_structure_stdlib(_STRUCTURES)}
        for plot in catalog.layouts:
            ref = structure_ref_of(plot)
            if ref is not None:
                self.assertIn(str(ref), stdlib_uids)
        structures = catalog.structures
        self.assertIn(
            BuildingPurpose.TAVERN,
            structures.leaves_of(inn),
        )
        cache = BuildingLayoutCache()
        layout = cache.ensure(_world(), inn)
        self.assertIsNotNone(layout)
        self.assertEqual(layout.occupied_footprint.width, 16)
        self.assertEqual(layout.occupied_footprint.depth, 16)
        self.assertFalse(layout.rooms)
        self.assertFalse(layout.cells)


if __name__ == "__main__":
    unittest.main()
