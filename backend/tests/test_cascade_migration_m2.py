"""Cascade-migration M2 — district/area/building scope ctx + Q4 stamps.

Covers tz_cascade_context §4/§8.4 for the migration slice:
- authored district ``system_economic_tier`` beats the template range
  and the inherited settlement tier (Q4);
- the effective district tier is stamped onto the extracted district
  ``NamedLocation`` and survives a ``load_topology_slots`` reload
  without re-rolling;
- a persisted building row with an authored tier participates as the
  building-scope link and its stamp is carried onto the re-extracted
  ``NamedLocation`` during regeneration.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from app.application.worldData.context.locationScope import (
    area_context,
    building_context,
    district_context,
    settlement_context,
)
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import (
    AreaSlot,
)
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import (
    StructureAreaAssembler,
)
from app.application.worldData.generators.assemblers.citySkeleton import (
    city_skeleton_from_settlement,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    district_templates,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    StructureGeneratorService,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    _district_named_location,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    load_topology_slots,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTypes import (
    district_type_entry,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    area_uid,
    building_location_uid,
    district_location_uid,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.dataModel.locations.settlement.district.districtTemplateEntry import (
    DistrictTemplateEntry,
)
from app.dataModel.locations.structure.building.buildingBodyTemplate import (
    BuildingBodyTemplate,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
)
from app.dataModel.locations.structure.building.structureCatalog import (
    StructureCatalog,
)
from app.dataModel.locations.structure.building.structureTemplate import (
    StructureTemplate,
)
from app.dataModel.spatial.facing import Facing
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _world() -> World:
    return World(
        world_uid="m2-world",
        name="M2",
        created_at="2026-01-01T00:00:00",
    )


def _settlement() -> NamedLocation:
    return NamedLocation(
        location_uid="m2-hold",
        world_uid="m2-world",
        display_name="Hold",
        system_location_type="settlement",
        created_at="2026-01-01T00:00:00",
        system_economic_tier="standard",
        map_x=0,
        map_y=0,
        map_z=0,
    )


def _district_template(range_: dict | None = None) -> DistrictTemplateEntry:
    return DistrictTemplateEntry(
        system_name="m2-district",
        display_name="District",
        district_type="residential",
        economic_tier_range=range_,
    )


def _district_row(tier: str | None) -> NamedLocation:
    return NamedLocation(
        location_uid=district_location_uid("m2-hold", "m2-district", 0),
        world_uid="m2-world",
        display_name="District",
        system_location_type=district_type_entry().system_type,
        created_at="2026-01-01T00:00:00",
        system_economic_tier=tier,
    )


def _slot(district_ctx) -> DistrictSlot:
    return DistrictSlot(
        origin_x=0,
        origin_y=0,
        width_fine=16,
        depth_fine=16,
        ground_z=7,
        district_template=_district_template(),
        slot_index=0,
        district_ctx=district_ctx,
    )


class DistrictScopeTest(unittest.TestCase):
    def test_authored_district_beats_range_and_inherited_settlement(self):
        world, settlement = _world(), _settlement()
        ctx = district_context(
            world,
            settlement_context(world, settlement),
            _district_template({"min": "poor", "max": "basic"}),
            district=_district_row("premium"),
            district_uid="d-1",
        )
        self.assertEqual(ctx.economic_tier, "premium")

    def test_range_materializes_anchored_to_inherited_settlement(self):
        world, settlement = _world(), _settlement()
        ctx = district_context(
            world,
            settlement_context(world, settlement),
            _district_template({"min": "standard", "max": "exceptional"}),
            district_uid="d-1",
        )
        # Anchor "standard" is inside the range → materializes to itself.
        self.assertEqual(ctx.economic_tier, "standard")

    def test_extracted_district_carries_effective_stamp(self):
        world, settlement = _world(), _settlement()
        template = _district_template({"min": "premium", "max": "exceptional"})
        ctx = district_context(
            world,
            settlement_context(world, settlement),
            template,
            district_uid="d-1",
        )
        self.assertIn(ctx.economic_tier, ("premium", "exceptional"))
        row = _district_named_location(settlement, _slot(ctx), slot_index=0)
        self.assertEqual(row.system_economic_tier, ctx.economic_tier)

    def test_reload_uses_persisted_stamp_without_reroll(self):
        world, settlement = _world(), _settlement()
        template = district_templates(world)[0]
        stamped = NamedLocation(
            location_uid=district_location_uid(
                settlement.location_uid, template.system_name, 0,
            ),
            world_uid=world.world_uid,
            display_name="District",
            system_location_type=district_type_entry().system_type,
            created_at="2026-01-01T00:00:00",
            system_economic_tier="premium",
        )
        stamped.district_topology = {
            "cell_x": 0, "cell_y": 0, "origin_x": 0, "origin_y": 0,
            "width_fine": 16, "depth_fine": 16, "ground_z": 7,
            "template_system_name": template.system_name, "slot_index": 0,
            "entries": [],
        }
        # The stamped value sits below the range — a fresh roll could
        # never produce it, so equality proves the stamp is the link.
        skeleton = city_skeleton_from_settlement(
            settlement, economic_tier="standard",
        )
        loaded = load_topology_slots(
            world, settlement, skeleton, [stamped],
            settlement_context(world, settlement),
        )
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded[0].district_ctx.economic_tier, "premium")


class BuildingScopeTest(unittest.TestCase):
    def setUp(self):
        self.world = _world()
        self.skeleton = city_skeleton_from_settlement(
            _settlement(), economic_tier="standard",
        )
        self.structure = StructureTemplate(
            system_name="00000000-0000-4000-8000-0000000000b1",
            display_name="Room",
            levels=[{
                "z_offset": 0, "display_name": "Ground",
                "rooms": [{
                    "room_id": "hall", "display_name": "Hall",
                    "room_type": "common_hall", "shape_type": "square",
                    "size": {"width_range": [5, 5]},
                    "required": True, "is_public": True,
                    "is_forbidden": False,
                }],
            }],
        )
        self.catalog = StructureCatalog([self.structure])
        self.plot = PlotLayoutTemplate(
            system_name="m2-plot",
            display_name="Plot",
            occupied_footprint={
                "min_x": 0, "min_y": 0, "width": 5, "depth": 5,
            },
            main_building=BuildingBodyTemplate(
                structure=self.structure.system_name,
                foundation_type="none",
                roof_type="none",
            ),
        )

    def _district_ctx(self):
        world = _world()
        return district_context(
            world,
            settlement_context(world, _settlement()),
            _district_template(),
            district_uid="m2-district-uid",
        )

    def test_authored_building_tier_survives_regeneration(self):
        world = self.world
        slot = AreaSlot(
            [(x, y) for x in range(20, 25) for y in range(30, 35)],
            7, Facing.SOUTH,
        )
        a_uid = area_uid("m2-district-uid", 20, 30, Facing.SOUTH)
        b_uid = building_location_uid(a_uid, self.plot.system_name, 20, 30)
        persisted = NamedLocation(
            location_uid=b_uid,
            world_uid=world.world_uid,
            display_name="House",
            system_location_type="building",
            created_at="2026-01-01T00:00:00",
            system_economic_tier="poor",
        )
        generate = StructureGeneratorService.generate_from_template
        seen = {}

        def capture(service, w, building, structure, **kwargs):
            seen["ctx"] = kwargs.get("ctx")
            return generate(service, w, building, structure, **kwargs)

        with patch.object(
            StructureGeneratorService, "generate_from_template", capture,
        ):
            area = StructureAreaAssembler().assemble(
                world, slot, self.plot, self.skeleton, None,
                structure_catalog=self.catalog,
                building_x=20, building_y=30,
                district_ctx=self._district_ctx(),
                district_uid="m2-district-uid",
                existing_buildings={b_uid: persisted},
            )
        self.assertEqual(seen["ctx"].economic_tier, "poor")
        self.assertEqual(
            area.building_location.system_economic_tier, "poor",
        )

    def test_fresh_building_nl_stamped_and_stable_on_regeneration(self):
        # M5 §8.4: every new NL in the chain carries the effective tier;
        # fed back as a persisted row it pins the same value (no re-roll).
        world = self.world
        slot = AreaSlot(
            [(x, y) for x in range(20, 25) for y in range(30, 35)],
            7, Facing.SOUTH,
        )
        plot = self.plot.model_copy(update={"economic_tier_band": "rich"})
        area = StructureAreaAssembler().assemble(
            world, slot, plot, self.skeleton, None,
            structure_catalog=self.catalog,
            building_x=20, building_y=30,
            district_ctx=self._district_ctx(),
            district_uid="m2-district-uid",
        )
        stamped = area.building_location
        self.assertEqual(stamped.system_economic_tier, "exceptional")

        a_uid = area_uid("m2-district-uid", 20, 30, Facing.SOUTH)
        b_uid = building_location_uid(a_uid, plot.system_name, 20, 30)
        # extract_settlement rewrites the probe uid to the persisted uid.
        persisted = replace(stamped, location_uid=b_uid)
        generate = StructureGeneratorService.generate_from_template
        seen = {}

        def capture(service, w, building, structure, **kwargs):
            seen["ctx"] = kwargs.get("ctx")
            return generate(service, w, building, structure, **kwargs)

        with patch.object(
            StructureGeneratorService, "generate_from_template", capture,
        ):
            StructureAreaAssembler().assemble(
                world, slot, plot, self.skeleton, None,
                structure_catalog=self.catalog,
                building_x=20, building_y=30,
                district_ctx=self._district_ctx(),
                district_uid="m2-district-uid",
                existing_buildings={b_uid: persisted},
            )
        self.assertEqual(seen["ctx"].economic_tier, "exceptional")

    def test_area_scope_materializes_once_per_scope(self):
        world = self.world
        district = self._district_ctx()
        plot = self.plot.model_copy(
            update={"economic_tier_band": "rich"},
        )
        first = area_context(world, district, plot, area_uid="a-1")
        again = area_context(world, district, plot, area_uid="a-1")
        self.assertEqual(first.economic_tier, "exceptional")
        self.assertEqual(first.economic_tier, again.economic_tier)
        building = NamedLocation(
            location_uid="b-1",
            world_uid=world.world_uid,
            display_name="House",
            system_location_type="building",
            created_at="2026-01-01T00:00:00",
        )
        b_ctx = building_context(world, first, building)
        self.assertEqual(b_ctx.economic_tier, first.economic_tier)


if __name__ == "__main__":
    unittest.main()
