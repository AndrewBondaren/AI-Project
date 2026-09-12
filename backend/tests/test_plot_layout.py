"""Plot drawing: envelope + nested building. No small outbuildings."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import (
    BuildingLayoutCache,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.dataModel.structure.building.buildingLayoutTemplate import (
    BuildingLayoutTemplate,
    interior_of,
    plot_has_building,
    try_building_layout,
)
from app.dataModel.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.dataModel.structure.enums.buildingPurpose import BuildingPurpose
from app.db.models.world import World

_REPO = Path(__file__).resolve().parents[2]
_TEMPLATES = _REPO / "fixtures" / "templates"


def _world() -> World:
    return World(
        world_uid="w-plot",
        name="plot",
        created_at="2026-01-01T00:00:00",
    )


class PlotLayoutContractTest(unittest.TestCase):
    def test_inn_small_wraps_tavern_1_fixture(self) -> None:
        plot_raw = json.loads((_TEMPLATES / "inn_small.json").read_text(encoding="utf-8"))
        tavern_raw = json.loads((_TEMPLATES / "tavern_1.json").read_text(encoding="utf-8"))
        plot = BuildingLayoutTemplate.model_validate(plot_raw)
        tavern = BuildingLayoutTemplate.model_validate(tavern_raw)

        self.assertEqual(plot.system_name, "inn_small")
        self.assertEqual(plot.structure_types, [BuildingPurpose.TAVERN])
        self.assertIsNotNone(plot.occupied_footprint)
        self.assertEqual(plot.occupied_footprint.width, 16)
        self.assertEqual(plot.occupied_footprint.depth, 16)
        self.assertTrue(plot_has_building(plot))
        interior = interior_of(plot)
        self.assertIsNotNone(interior)
        self.assertEqual(interior.system_name, "tavern_1")
        self.assertEqual(interior.levels, tavern.levels)
        self.assertFalse(plot.levels)

    def test_try_layout_accepts_plot_without_root_levels(self) -> None:
        raw = json.loads((_TEMPLATES / "inn_small.json").read_text(encoding="utf-8"))
        layout = try_building_layout(raw)
        self.assertIsNotNone(layout)
        self.assertEqual(layout.system_name, "inn_small")

    def test_try_layout_still_skips_outline(self) -> None:
        outline = BuildingTemplateOutline(
            system_name="tavern_lib",
            structure_type="tavern",
            display_name="Tavern",
        )
        self.assertIsNone(try_building_layout(outline.model_dump(mode="json")))

    def test_plaza_plot_has_no_building(self) -> None:
        plaza = BuildingLayoutTemplate(
            system_name="plaza_1",
            structure_type="plaza",
            display_name="Площадь",
            occupied_footprint={"width": 8, "depth": 8},
        )
        self.assertFalse(plot_has_building(plaza))
        self.assertIsNone(interior_of(plaza))
        self.assertIsNotNone(try_building_layout(plaza.model_dump(mode="json")))

    def test_leftover_root_levels_still_count_as_building(self) -> None:
        leftover = BuildingLayoutTemplate(
            system_name="town_hall",
            structure_type="town_hall",
            display_name="Ратуша",
            occupied_footprint={"width": 4, "depth": 4},
            levels=[{"z_offset": 0, "rooms": [{"room_id": "hall"}]}],
        )
        self.assertTrue(plot_has_building(leftover))
        self.assertIs(interior_of(leftover), leftover)

    def test_catalog_inn_small_and_cache_envelope(self) -> None:
        catalog = assemble_building_catalog(_world())
        inn = catalog.by_system_name("inn_small")
        self.assertIsNotNone(inn)
        self.assertTrue(plot_has_building(inn))
        self.assertEqual(interior_of(inn).system_name, "tavern_1")
        cache = BuildingLayoutCache()
        layout = cache.ensure(_world(), inn)
        self.assertIsNotNone(layout)
        self.assertEqual(layout.occupied_footprint.width, 16)
        self.assertEqual(layout.occupied_footprint.depth, 16)
        self.assertFalse(layout.rooms)
        self.assertFalse(layout.cells)


if __name__ == "__main__":
    unittest.main()
