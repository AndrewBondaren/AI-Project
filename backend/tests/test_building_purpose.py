"""Engine BuildingPurpose catalog, like/strict, pin vs purpose pool."""

from __future__ import annotations

import unittest

from app.dataModel.settlement.district.allowedStructureTypes import (
    allowed_fill_structure_types,
    district_hosts_purpose,
)
from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.settlement.district.requiredStructureResolve import (
    resolve_required_layouts,
    unhosted_settlement_types,
    union_required_structures,
)
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.dataModel.structure.building.buildingTemplateOutline import BuildingTemplateOutline
from app.dataModel.structure.enums.buildingPurpose import (
    BuildingPurpose,
    BuildingPurposeMatch,
    coerce_purpose_list,
    coerce_purpose_match,
    primary_purpose,
    purposes_match,
    union_plot_purposes,
)


def _layout(
    system_name: str,
    structure_type: str | list[str] | None = None,
    **kwargs,
) -> BuildingLayoutTemplate:
    payload: dict = {
        "system_name": system_name,
        "display_name": system_name,
        "levels": [{"z_offset": 0, "rooms": []}],
    }
    if structure_type is not None:
        if isinstance(structure_type, list):
            payload["structure_types"] = structure_type
        else:
            payload["structure_type"] = structure_type
    payload.update(kwargs)
    return BuildingLayoutTemplate.model_validate(payload)


class CoercePurposeTest(unittest.TestCase):
    def test_omit_building_is_house(self) -> None:
        layout = _layout("hut_1")
        self.assertEqual(layout.structure_types, [BuildingPurpose.HOUSE])
        self.assertEqual(layout.structure_type, "house")

    def test_scalar_alias(self) -> None:
        layout = _layout("tavern_1", "tavern")
        self.assertEqual(layout.structure_types, [BuildingPurpose.TAVERN])
        self.assertEqual(layout.structure_type, "tavern")

    def test_array_and_unknown_dropped(self) -> None:
        layout = _layout("combo_1", ["house", "workshop", "blacksmith", "house"])
        self.assertEqual(
            layout.structure_types,
            [BuildingPurpose.HOUSE, BuildingPurpose.WORKSHOP],
        )

    def test_empty_allowed_stays_empty(self) -> None:
        self.assertEqual(coerce_purpose_list([], empty_as_house=False), [])
        self.assertEqual(
            coerce_purpose_list(None, empty_as_house=False),
            [],
        )

    def test_outline_omit_and_alias(self) -> None:
        omit = BuildingTemplateOutline(system_name="a", display_name="A")
        self.assertEqual(omit.structure_types, [BuildingPurpose.HOUSE])
        aliased = BuildingTemplateOutline.model_validate({
            "system_name": "b",
            "display_name": "B",
            "structure_type": "smithy",
        })
        self.assertEqual(aliased.structure_types, [BuildingPurpose.SMITHY])


class MatchAndUnionTest(unittest.TestCase):
    def test_like_vs_strict(self) -> None:
        combo = [BuildingPurpose.HOUSE, BuildingPurpose.WORKSHOP]
        filt = [BuildingPurpose.WORKSHOP]
        self.assertTrue(purposes_match(combo, filt, BuildingPurposeMatch.LIKE))
        self.assertFalse(purposes_match(combo, filt, BuildingPurposeMatch.STRICT))
        self.assertTrue(
            purposes_match(
                [BuildingPurpose.WORKSHOP], filt, BuildingPurposeMatch.STRICT,
            )
        )

    def test_union_plot_purposes(self) -> None:
        a = _layout("w", ["workshop"])
        b = _layout("h", ["house"])
        self.assertEqual(
            union_plot_purposes([a, b]),
            (BuildingPurpose.WORKSHOP, BuildingPurpose.HOUSE),
        )

    def test_primary_purpose(self) -> None:
        self.assertEqual(
            primary_purpose([BuildingPurpose.INN, BuildingPurpose.TAVERN]),
            BuildingPurpose.INN,
        )
        self.assertEqual(primary_purpose([]), BuildingPurpose.HOUSE)

    def test_coerce_match_default_like(self) -> None:
        self.assertEqual(coerce_purpose_match(None), BuildingPurposeMatch.LIKE)
        self.assertEqual(coerce_purpose_match("strict"), BuildingPurposeMatch.STRICT)


class CatalogAndPinTest(unittest.TestCase):
    def test_of_structure_type_membership(self) -> None:
        catalog = BuildingCatalog.from_layouts([
            _layout("house_1", "house"),
            _layout("combo_1", ["house", "workshop"]),
            _layout("shop_1", "shop"),
        ])
        names = [row.system_name for row in catalog.of_structure_type("workshop")]
        self.assertEqual(names, ["combo_1"])
        self.assertEqual(
            sorted(catalog.structure_types()),
            ["house", "shop", "workshop"],
        )

    def test_matching_allowed_like_keeps_combo(self) -> None:
        catalog = BuildingCatalog.from_layouts([
            _layout("combo_1", ["house", "workshop"]),
            _layout("pure_ws", "workshop"),
        ])
        like = catalog.matching_allowed(
            catalog.layouts, [BuildingPurpose.WORKSHOP], "like",
        )
        self.assertEqual([row.system_name for row in like], ["combo_1", "pure_ws"])
        strict = catalog.matching_allowed(
            catalog.layouts, [BuildingPurpose.WORKSHOP], "strict",
        )
        self.assertEqual([row.system_name for row in strict], ["pure_ws"])

    def test_pin_is_system_name_not_purpose_pool(self) -> None:
        catalog = BuildingCatalog.from_layouts([
            _layout("tavern_1", "tavern"),
            _layout("tavern_2", "tavern"),
        ])
        pool = resolve_required_layouts(
            RequiredStructure(building_template="x", structure_type="tavern"),
            catalog,
        )
        self.assertEqual([row.system_name for row in pool], ["tavern_1", "tavern_2"])
        pin_miss = resolve_required_layouts(
            RequiredStructure(building_template="tavern"),
            catalog,
        )
        self.assertEqual(pin_miss, ())
        pin_hit = resolve_required_layouts(
            RequiredStructure(building_template="tavern_1"),
            catalog,
        )
        self.assertEqual([row.system_name for row in pin_hit], ["tavern_1"])


class HostAndFillTest(unittest.TestCase):
    def test_hosts_omit_empty_list(self) -> None:
        self.assertTrue(district_hosts_purpose(None, "mine"))
        self.assertFalse(district_hosts_purpose([], "mine"))
        self.assertTrue(district_hosts_purpose([BuildingPurpose.MINE], "mine"))
        self.assertFalse(district_hosts_purpose([BuildingPurpose.MINE], "tavern"))

    def test_union_required_only_hosted_types(self) -> None:
        district = [RequiredStructure(building_template="town_hall", count=1)]
        merged = union_required_structures(
            ["town_hall", "mine"],
            district,
            [BuildingPurpose.TOWN_HALL],
        )
        self.assertEqual(
            [row.structure_type for row in merged],
            [BuildingPurpose.TOWN_HALL],
        )
        open_host = union_required_structures(
            ["town_hall", "mine"],
            district,
            None,
        )
        self.assertEqual(
            [str(row.structure_type) for row in open_host],
            ["town_hall", "mine"],
        )

    def test_unhosted_leftover(self) -> None:
        leftover = unhosted_settlement_types(
            ["mine", "tavern", "blacksmith"],
            [[BuildingPurpose.TOWN_HALL], []],
        )
        self.assertEqual(leftover, ("mine", "tavern", "blacksmith"))
        hosted = unhosted_settlement_types(
            ["mine"],
            [None, [BuildingPurpose.MINE]],
        )
        self.assertEqual(hosted, ())

    def test_allowed_fill_drops_unknown(self) -> None:
        catalog_types = ("tavern", "house")
        self.assertEqual(
            allowed_fill_structure_types(["tavern", "blacksmith"], catalog_types),
            ("tavern",),
        )


if __name__ == "__main__":
    unittest.main()
