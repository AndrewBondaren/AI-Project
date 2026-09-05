"""CITY-T-2a…2d — recipe, catalog, cell rng, required resolve, district select, path 3."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.worldRow import location_types
from app.application.worldData.buildingTemplateLibraryService import BuildingTemplateLibraryService
from app.application.worldData.generators.assemblers.citySkeleton import (
    city_skeleton_from_settlement,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.tokens import (
    build_tokens,
    candidate_template_names,
)
from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import (
    BuildingLayoutCache,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import (
    plan_district_slots,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.generators.coordinates.settlementCellRng import (
    SettlementCellRngRole,
    settlement_cell_rng,
)
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.dataModel.locations.locationType.locationTypeSubtypeEntry import (
    LocationTypeSubtypeEntry,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.settlement.district.allowedStructureTypes import (
    allowed_fill_structure_types,
)
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.settlement.district.requiredStructureResolve import (
    resolve_required_layouts,
    union_required_structures,
)
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import (
    BuildingLayoutTemplate,
    try_building_layout,
)
from app.dataModel.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _layout(system_name: str, structure_type: str) -> BuildingLayoutTemplate:
    return BuildingLayoutTemplate(
        system_name=system_name,
        structure_type=structure_type,
        display_name=system_name,
        levels=[{"z_offset": 0, "rooms": []}],
    )


def _world(**kwargs) -> World:
    payload = {
        "world_uid": "w1",
        "name": "Test",
        "created_at": "2026-01-01T00:00:00",
        "map_cell_size_m": 3000,
        "city_size_registry": [
            {"system_size": "city", "display_size": "City", "footprint_multiplier": 2.0},
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
            {"system_size": "hamlet", "display_size": "Hamlet", "footprint_multiplier": 1.0},
        ],
    }
    payload.update(kwargs)
    return World(**payload)


def _settlement(*, subtype: str | None, size: str = "city", loc_type: str = "settlement") -> NamedLocation:
    loc = NamedLocation(
        location_uid="loc-1",
        world_uid="w1",
        display_name="Hold",
        system_location_type=loc_type,
        created_at="2026-01-01T00:00:00",
        system_location_subtype=subtype,
        system_city_size=size,
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )
    loc.settlement_density = "medium"
    return loc


def _skeleton(world: World, settlement: NamedLocation):
    return city_skeleton_from_settlement(
        settlement,
        economic_tier=TierResolver.resolve(world=world, city=settlement),
    )


class RecipePojoTest(unittest.TestCase):
    def test_engine_city_village_dungeon_recipes(self) -> None:
        engine = WorldLocationTypeRegistry.canonical_engine()
        city = engine.subtype_for("settlement", "city")
        village = engine.subtype_for("settlement", "village")
        dungeon = engine.subtype_for("settlement", "dungeon")
        underground = engine.subtype_for("settlement", "underground_city")
        assert city is not None and village is not None
        assert dungeon is not None and underground is not None
        self.assertEqual(
            city.typical_district_types,
            ["civic", "commercial", "residential", "industrial", "port"],
        )
        self.assertEqual(city.required_structure_types, ["town_hall"])
        self.assertTrue(city.has_district_recipe())
        self.assertEqual(village.typical_district_types, ["civic", "residential"])
        self.assertEqual(village.required_structure_types, [])
        self.assertTrue(village.has_district_recipe())
        self.assertFalse(dungeon.has_district_recipe())
        self.assertEqual(underground.typical_district_types, ["civic", "residential"])

    def test_geographic_extra_keys_ignored(self) -> None:
        row = LocationTypeSubtypeEntry.model_validate({
            "system_subtype": "mountain",
            "unknown_master_key": True,
            "typical_district_types": ["civic"],
        })
        self.assertEqual(row.system_subtype, "mountain")
        self.assertFalse(hasattr(row, "unknown_master_key"))


class AllowedAndRequiredTest(unittest.TestCase):
    def test_allowed_null_empty_list(self) -> None:
        catalog_types = ("tavern", "house")
        self.assertEqual(
            allowed_fill_structure_types(None, catalog_types),
            ("house", "tavern"),
        )
        self.assertEqual(allowed_fill_structure_types([], catalog_types), ())
        self.assertEqual(
            allowed_fill_structure_types(["tavern", "tavern"], catalog_types),
            ("tavern",),
        )

    def test_resolve_required_type_then_name(self) -> None:
        catalog = BuildingCatalog.from_layouts([
            _layout("tavern_1", "tavern"),
            _layout("tavern_2", "tavern"),
            _layout("town_hall", "building"),
        ])
        as_type = resolve_required_layouts(
            RequiredStructure(building_template="x", structure_type="tavern"),
            catalog,
        )
        self.assertEqual([row.system_name for row in as_type], ["tavern_1", "tavern_2"])
        as_name_type = resolve_required_layouts(
            RequiredStructure(building_template="tavern"),
            catalog,
        )
        self.assertEqual([row.system_name for row in as_name_type], ["tavern_1", "tavern_2"])
        as_system = resolve_required_layouts(
            RequiredStructure(building_template="town_hall"),
            catalog,
        )
        self.assertEqual([row.system_name for row in as_system], ["town_hall"])

    def test_union_required_settlement_first(self) -> None:
        district = [RequiredStructure(building_template="town_hall", count=1)]
        merged = union_required_structures(["town_hall", "market"], district)
        self.assertEqual(
            [row.building_template for row in merged],
            ["town_hall", "market"],
        )


class CatalogAndRngTest(unittest.TestCase):
    def test_catalog_order_and_last_wins(self) -> None:
        catalog = BuildingCatalog.from_layouts([
            _layout("b_inn", "tavern"),
            _layout("a_hall", "civic"),
            BuildingLayoutTemplate(
                system_name="b_inn",
                structure_type="tavern",
                display_name="override",
            ),
        ])
        self.assertEqual([row.system_name for row in catalog.layouts], ["a_hall", "b_inn"])
        self.assertEqual(catalog.by_system_name("b_inn").display_name, "override")
        self.assertEqual(
            [row.system_name for row in catalog.of_structure_type("tavern")],
            ["b_inn"],
        )

    def test_try_building_layout_skips_outline(self) -> None:
        outline = BuildingTemplateOutline(
            system_name="tavern_lib",
            structure_type="tavern",
            display_name="Tavern",
        )
        self.assertIsNone(try_building_layout(outline.model_dump(mode="json")))

    def test_assemble_catalog_path3_builtins(self) -> None:
        catalog = assemble_building_catalog(_world())
        self.assertIsNotNone(catalog.by_system_name("town_hall"))
        self.assertIsNotNone(catalog.by_system_name("inn_small"))

    def test_cell_rng_stable_and_independent(self) -> None:
        a = settlement_cell_rng("w", "c", 1, 2, SettlementCellRngRole.BUILDINGS)
        b = settlement_cell_rng("w", "c", 1, 2, "buildings")
        pool = ["tavern_1", "tavern_2", "tavern_3"]
        self.assertEqual(a.choice(pool), b.choice(pool))
        other_cell = settlement_cell_rng("w", "c", 1, 3, SettlementCellRngRole.BUILDINGS)
        same_cell_districts = settlement_cell_rng(
            "w", "c", 1, 2, SettlementCellRngRole.DISTRICTS,
        )
        buildings_a = settlement_cell_rng("w", "c", 1, 2, SettlementCellRngRole.BUILDINGS).random()
        buildings_b = other_cell.random()
        districts_a = same_cell_districts.random()
        self.assertNotEqual(buildings_a, buildings_b)
        self.assertNotEqual(
            settlement_cell_rng("w", "c", 1, 2, SettlementCellRngRole.BUILDINGS).random(),
            districts_a,
        )


class JsonValidationRecipeTest(unittest.TestCase):
    def test_empty_world_reads_engine_city_recipe(self) -> None:
        city = location_types(SimpleNamespace(world_uid="w")).subtype_for("settlement", "city")
        assert city is not None
        self.assertTrue(city.has_district_recipe())
        self.assertEqual(city.required_structure_types, ["town_hall"])

    def test_world_subtype_overlays_recipe_keeps_other_engine_subtypes(self) -> None:
        world = SimpleNamespace(
            world_uid="w1",
            location_type_registry=[{
                "system_type": "settlement",
                "display_type": "Поселение",
                "subtypes": [{
                    "system_subtype": "city",
                    "typical_district_types": ["residential"],
                }],
            }],
        )
        reg = location_types(world)
        city = reg.subtype_for("settlement", "city")
        village = reg.subtype_for("settlement", "village")
        assert city is not None and village is not None
        self.assertEqual(city.typical_district_types, ["residential"])
        self.assertTrue(village.has_district_recipe())

    def test_import_geographic_extra_key_not_422(self) -> None:
        out = normalize_world({
            "name": "T",
            "created_at": "2026-01-01T00:00:00",
            "location_type_registry": {
                "geographic": {
                    "display_name": "География",
                    "subtypes": [{
                        "system_subtype": "mountain",
                        "unknown_master_key": True,
                    }],
                },
            },
        })
        self.assertTrue(out["location_type_registry"])


class LibraryHydrateTest(unittest.IsolatedAsyncioTestCase):
    async def test_layouts_for_world_skips_outline(self) -> None:
        layout = _layout("tavern_1", "tavern")
        outline = BuildingTemplateOutline(
            system_name="tavern_outline",
            structure_type="tavern",
            display_name="Outline",
        )
        rows = {
            "uid-ok": BuildingTemplateRow(
                template_uid="uid-ok",
                system_name="tavern_1",
                display_name="Tavern",
                structure_type="tavern",
                data=layout.model_dump(mode="json"),
            ),
            "uid-outline": BuildingTemplateRow(
                template_uid="uid-outline",
                system_name="tavern_outline",
                display_name="Outline",
                structure_type="tavern",
                data=outline.model_dump(mode="json"),
            ),
        }
        repo = MagicMock()
        repo.get_by_uid = AsyncMock(side_effect=lambda uid: rows.get(uid))
        service = BuildingTemplateLibraryService(repo=repo, world_service=MagicMock())
        world = SimpleNamespace(
            world_uid="w1",
            building_template_registry=[
                {"system_template_uid": "uid-ok"},
                {"system_template_uid": "uid-outline"},
            ],
        )
        got = await service.layouts_for_world(world)
        self.assertEqual([row.system_name for row in got], ["tavern_1"])


class DistrictSelectTest(unittest.TestCase):
    def test_legacy_without_subtype_keeps_civic_center(self) -> None:
        world = _world()
        settlement = _settlement(subtype=None, loc_type="city")
        slots = plan_district_slots(world, settlement, _skeleton(world, settlement), None)
        civic = [slot for slot in slots if slot.district_template.system_name == "civic_center"]
        self.assertTrue(civic)
        self.assertTrue(all(slot.cell_x is not None for slot in slots))

    def test_recipe_city_types_are_typical_only(self) -> None:
        world = _world()
        settlement = _settlement(subtype="city", size="city")
        slots = plan_district_slots(world, settlement, _skeleton(world, settlement), None)
        types = {slot.district_template.district_type for slot in slots}
        typical = set(
            WorldLocationTypeRegistry.canonical_engine()
            .subtype_for("settlement", "city")
            .typical_district_types
        )
        self.assertTrue(types)
        self.assertTrue(types <= typical)
        self.assertNotIn("military", types)
        center = next(slot for slot in slots if slot.cell_x == 1 and slot.cell_y == 1)
        self.assertEqual(center.district_template.district_type, "civic")
        req_names = {row.building_template for row in center.required_structures}
        self.assertIn("town_hall", req_names)

    def test_recipe_unknown_subtype_is_legacy(self) -> None:
        world = _world()
        settlement = _settlement(subtype="not_a_real_subtype", size="city")
        slots = plan_district_slots(world, settlement, _skeleton(world, settlement), None)
        self.assertTrue(slots)


class TokenPickTest(unittest.TestCase):
    def test_one_drawing_per_type_not_per_file(self) -> None:
        catalog = BuildingCatalog.from_layouts([
            _layout("tavern_1", "tavern"),
            _layout("tavern_2", "tavern"),
            _layout("tavern_3", "tavern"),
        ])
        template = DistrictTemplateEntry(
            system_name="inn_row",
            display_name="Inns",
            district_type="commercial",
            allowed_structure_types=["tavern"],
        )
        slot = DistrictSlot(
            origin_x=0, origin_y=0, width_m=40, depth_m=40, ground_z=0,
            district_template=template,
            cell_x=0, cell_y=0,
        )
        world = _world()
        skeleton = _skeleton(world, _settlement(subtype="city"))
        rng = settlement_cell_rng("w1", "loc-1", 0, 0, SettlementCellRngRole.BUILDINGS)
        names = candidate_template_names(
            slot, BuildingLayoutCache(), world, skeleton, catalog=catalog, rng=rng,
        )
        self.assertEqual(len(names), 1)
        self.assertIn(names[0], {"tavern_1", "tavern_2", "tavern_3"})
        rng2 = settlement_cell_rng("w1", "loc-1", 0, 0, SettlementCellRngRole.BUILDINGS)
        names2 = candidate_template_names(
            slot, BuildingLayoutCache(), world, skeleton, catalog=catalog, rng=rng2,
        )
        self.assertEqual(names, names2)

    def test_structure_counts_copies_chosen_drawing(self) -> None:
        catalog = BuildingCatalog.from_layouts([_layout("tavern_1", "tavern")])
        template = DistrictTemplateEntry(
            system_name="inn_row",
            display_name="Inns",
            district_type="commercial",
            allowed_structure_types=["tavern"],
            structure_counts={"tavern_1": 3},
        )
        slot = DistrictSlot(
            origin_x=0, origin_y=0, width_m=40, depth_m=40, ground_z=0,
            district_template=template,
            cell_x=1, cell_y=1,
        )
        world = _world()
        skeleton = _skeleton(world, _settlement(subtype="city"))
        from app.application.worldData.generators.structure.structureGeneratorService import (
            OccupiedFootprint,
            StructureLayout,
        )
        layout = StructureLayout(
            cells=[],
            levels=[],
            passages=[],
            rooms=[],
            occupied_footprint=OccupiedFootprint(min_x=0, min_y=0, width=4, depth=4),
        )
        cache = BuildingLayoutCache.from_south_map({"tavern_1": layout})
        rng = settlement_cell_rng("w1", "loc-1", 1, 1, SettlementCellRngRole.BUILDINGS)
        tokens = build_tokens(slot, cache, world, skeleton, catalog=catalog, rng=rng)
        self.assertEqual(len(tokens), 3)
        self.assertEqual({token.system_name for token in tokens}, {"tavern_1"})


class Path3GenerateTest(unittest.TestCase):
    def test_generate_layout_catalog_none_replay_same_drawings(self) -> None:
        world = _world(
            map_cell_size_m=16,
            city_size_registry=[
                {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
            ],
        )
        settlement = _settlement(subtype="city", size="town")
        service = SettlementGeneratorService()
        first = service.generate_layout(world, settlement, catalog=None)
        second = service.generate_layout(world, settlement, catalog=None)
        self.assertTrue(first.district_layouts)
        types = {
            layout.slot.district_template.district_type for layout in first.district_layouts
        }
        typical = set(
            WorldLocationTypeRegistry.canonical_engine()
            .subtype_for("settlement", "city")
            .typical_district_types
        )
        self.assertTrue(types <= typical)
        first_slots = [
            (layout.slot.cell_x, layout.slot.cell_y, layout.slot.district_template.system_name)
            for layout in first.district_layouts
        ]
        second_slots = [
            (layout.slot.cell_x, layout.slot.cell_y, layout.slot.district_template.system_name)
            for layout in second.district_layouts
        ]
        self.assertEqual(first_slots, second_slots)
        first_names = [
            (layout.slot.cell_x, layout.slot.cell_y, area.building_location.system_template_uid)
            for layout in first.district_layouts
            for area in layout.area_layouts
            if area.building_location is not None
        ]
        second_names = [
            (layout.slot.cell_x, layout.slot.cell_y, area.building_location.system_template_uid)
            for layout in second.district_layouts
            for area in layout.area_layouts
            if area.building_location is not None
        ]
        self.assertEqual(first_names, second_names)


if __name__ == "__main__":
    unittest.main()
