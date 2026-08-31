"""Outdoor extract / C6 target / C20 front door."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import (
    AreaThreshold,
    AreaThresholdKind,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import (
    DistrictLayout,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    StructureLayout,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    SettlementOutdoorExtractError,
    extract_settlement,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    is_settlement_outdoor_target,
)
from app.dataModel.locations.enums.entryRole import EntryRole
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.enums.passageType import PassageType
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.namedLocation import NamedLocation


def _settlement() -> NamedLocation:
    return NamedLocation(
        location_uid="set-1",
        world_uid="w1",
        display_name="Town",
        system_location_type="settlement",
        created_at="2026-01-01T00:00:00",
        map_x=0,
        map_y=0,
        map_z=0,
        system_city_size="hamlet",
    )


def _layout(*, passages: list[LocationPassage]) -> SettlementLayout:
    template = DistrictTemplateEntry(
        system_name="core",
        display_name="Core",
        district_type="civic",
    )
    dslot = DistrictSlot(
        origin_x=0,
        origin_y=0,
        width_m=10,
        depth_m=10,
        ground_z=0,
        district_template=template,
    )
    aslot = AreaSlot(cells=[(0, 0), (1, 0)], ground_z=0, facing=Facing.SOUTH)
    threshold = AreaThreshold(
        kind=AreaThresholdKind.DOOR, cells=[(0, 0)], z=0,
    )
    probe = NamedLocation(
        location_uid="probe-hut-0-0",
        world_uid="w1",
        display_name="Hut",
        system_location_type="building",
        created_at="2026-01-01T00:00:00",
        map_x=0,
        map_y=0,
        map_z=0,
        system_template_uid="hut",
    )
    level = LocationLevel(
        level_uid="old-level",
        location_uid="probe-hut-0-0",
        z=0,
        z_height=3,
        display_name="ground",
    )
    building_layout = StructureLayout(
        cells=[],
        levels=[level],
        passages=passages,
        rooms=[],
    )
    area = AreaLayout(
        slot=aslot,
        threshold=threshold,
        building_location=probe,
        building_layout=building_layout,
    )
    district = DistrictLayout(slot=dslot, area_layouts=[area])
    return SettlementLayout(district_layouts=[district])


class TestSettlementOutdoorExtract(unittest.TestCase):

    def test_c6_settlement_yes_district_no(self):
        self.assertTrue(is_settlement_outdoor_target(_settlement()))
        district = NamedLocation(
            location_uid="d1",
            world_uid="w1",
            display_name="Core",
            system_location_type="district",
            created_at="2026-01-01T00:00:00",
        )
        self.assertFalse(is_settlement_outdoor_target(district))

    def test_c20_missing_front_raises(self):
        with self.assertRaises(SettlementOutdoorExtractError):
            extract_settlement(_settlement(), _layout(passages=[]))

    def test_front_entry_and_district_parent(self):
        passage = LocationPassage(
            passage_uid="p-front",
            world_uid="w1",
            to_level_uid="old-level",
            to_x=1,
            to_y=0,
            system_passage_type=PassageType.MAIN_ENTRANCE,
            from_level_uid=None,
        )
        extracted = extract_settlement(_settlement(), _layout(passages=[passage]))
        self.assertEqual(len(extracted.districts), 1)
        self.assertEqual(len(extracted.buildings), 1)
        self.assertEqual(
            extracted.buildings[0].parent_location_uid,
            extracted.districts[0].location_uid,
        )
        self.assertEqual(len(extracted.entry_points), 1)
        self.assertEqual(extracted.entry_points[0].entry_role, EntryRole.FRONT.value)
        self.assertTrue(extracted.entry_points[0].is_discovered)
        self.assertEqual(extracted.wire.settlement_uid, "set-1")
        self.assertEqual(len(extracted.wire.districts), 1)

    def test_plot_without_building_skips_c20(self):
        template = DistrictTemplateEntry(
            system_name="core",
            display_name="Core",
            district_type="civic",
        )
        dslot = DistrictSlot(
            origin_x=0, origin_y=0, width_m=10, depth_m=10, ground_z=0,
            district_template=template,
        )
        aslot = AreaSlot(cells=[(0, 0), (1, 0), (0, 1), (1, 1)], ground_z=2, facing=Facing.SOUTH)
        threshold = AreaThreshold(
            kind=AreaThresholdKind.PARCEL_EDGE, cells=[(0, 0)], z=2,
        )
        area = AreaLayout(slot=aslot, threshold=threshold)
        district = DistrictLayout(slot=dslot, area_layouts=[area])
        extracted = extract_settlement(_settlement(), SettlementLayout(district_layouts=[district]))
        self.assertEqual(len(extracted.buildings), 0)
        self.assertEqual(len(extracted.entry_points), 0)
        self.assertEqual(len(extracted.wire.districts[0].areas), 1)
        self.assertEqual(extracted.wire.districts[0].areas[0].buildings, [])
        self.assertEqual(extracted.wire.districts[0].areas[0].slot.ground_z, 2)


if __name__ == "__main__":
    unittest.main()
