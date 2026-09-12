"""Engine BuildingPurpose catalog, like/strict, pin vs purpose pool."""

from __future__ import annotations

import unittest

from types import SimpleNamespace

from app.application.jsonValidation.worldRow import enabled_building_purposes, purpose_packs
from app.dataModel.settlement.district.allowedStructureTypes import (
    allowed_fill_structure_types,
    district_hosts_purpose,
)
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
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
    FAMILY_OF,
    BuildingPurpose,
    BuildingPurposeFamily,
    BuildingPurposeMatch,
    PurposePack,
    WorldPurposePacks,
    coerce_allowed_list,
    coerce_purpose_list,
    coerce_purpose_match,
    expand_allowed,
    primary_purpose,
    purposes_for_world,
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


    def test_drawing_family_tag_dropped_to_house(self) -> None:
        layout = _layout("bad_1", ["trade"])
        self.assertEqual(layout.structure_types, [BuildingPurpose.HOUSE])
        scalar = _layout("bad_2", "trade")
        self.assertEqual(scalar.structure_types, [BuildingPurpose.HOUSE])


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

    def test_family_host_and_fill(self) -> None:
        self.assertTrue(
            district_hosts_purpose([BuildingPurposeFamily.TRADE], "tavern"),
        )
        self.assertFalse(
            district_hosts_purpose([BuildingPurposeFamily.TRADE], "temple"),
        )
        catalog_types = ("tavern", "shop", "temple", "house")
        self.assertEqual(
            allowed_fill_structure_types(["trade"], catalog_types),
            ("shop", "tavern"),
        )
        district = DistrictTemplateEntry.model_validate({
            "system_name": "market",
            "display_name": "Market",
            "district_type": "commercial",
            "allowed_structure_types": ["trade"],
        })
        self.assertEqual(
            district.allowed_structure_types,
            [BuildingPurposeFamily.TRADE],
        )


class PurposeTreeAndPacksTest(unittest.TestCase):
    def test_family_of_new_leaves(self) -> None:
        self.assertEqual(FAMILY_OF[BuildingPurpose.CAFE], BuildingPurposeFamily.TRADE)
        self.assertEqual(FAMILY_OF[BuildingPurpose.CHURCH], BuildingPurposeFamily.PUBLIC)
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.COURTHOUSE],
            BuildingPurposeFamily.PUBLIC,
        )
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.PRISON],
            BuildingPurposeFamily.DEFENSE,
        )
        self.assertEqual(FAMILY_OF[BuildingPurpose.PORTAL], BuildingPurposeFamily.TRANSIT)
        public_leaves = expand_allowed(["public"])
        self.assertIn(BuildingPurpose.COURTHOUSE, public_leaves)
        self.assertNotIn(BuildingPurpose.PRISON, public_leaves)
        self.assertIn(BuildingPurpose.PRISON, expand_allowed(["defense"]))
        self.assertFalse(
            purposes_match(
                [BuildingPurpose.PRISON],
                [BuildingPurposeFamily.PUBLIC],
                BuildingPurposeMatch.LIKE,
            )
        )
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.ASSEMBLY_PLANT],
            BuildingPurposeFamily.FACTORY,
        )
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.PALACE],
            BuildingPurposeFamily.GOVERNMENT,
        )
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.LEGISLATURE],
            BuildingPurposeFamily.GOVERNMENT,
        )
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.CHANCERY],
            BuildingPurposeFamily.GOVERNMENT,
        )
        gov = expand_allowed(["government"])
        self.assertEqual(
            set(gov),
            {
                BuildingPurpose.PALACE,
                BuildingPurpose.LEGISLATURE,
                BuildingPurpose.CHANCERY,
            },
        )
        self.assertNotIn(BuildingPurpose.PALACE, expand_allowed(["public"]))
        self.assertNotIn(BuildingPurpose.PALACE, expand_allowed(["dwelling"]))
        self.assertFalse(
            purposes_match(
                [BuildingPurpose.PALACE],
                [BuildingPurposeFamily.PUBLIC],
                BuildingPurposeMatch.LIKE,
            )
        )
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.ACADEMY],
            BuildingPurposeFamily.KNOWLEDGE,
        )
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.LABORATORY],
            BuildingPurposeFamily.KNOWLEDGE,
        )
        self.assertEqual(
            FAMILY_OF[BuildingPurpose.ARCANE_LAB],
            BuildingPurposeFamily.KNOWLEDGE,
        )
        self.assertNotIn(BuildingPurpose.LIBRARY, expand_allowed(["knowledge"]))
        self.assertNotIn(BuildingPurpose.SCHOOL, expand_allowed(["knowledge"]))
        self.assertFalse(
            purposes_match(
                [BuildingPurpose.ARCANE_LAB],
                [BuildingPurposeFamily.PUBLIC],
                BuildingPurposeMatch.LIKE,
            )
        )

    def test_expand_trade_not_temple(self) -> None:
        leaves = expand_allowed(["trade"])
        self.assertIn(BuildingPurpose.TAVERN, leaves)
        self.assertIn(BuildingPurpose.SHOP, leaves)
        self.assertNotIn(BuildingPurpose.TEMPLE, leaves)

    def test_like_family_match(self) -> None:
        self.assertTrue(
            purposes_match(
                [BuildingPurpose.TAVERN],
                [BuildingPurposeFamily.TRADE],
                BuildingPurposeMatch.LIKE,
            )
        )
        self.assertFalse(
            purposes_match(
                [BuildingPurpose.TEMPLE],
                [BuildingPurposeFamily.TRADE],
                BuildingPurposeMatch.LIKE,
            )
        )
        catalog = BuildingCatalog.from_layouts([
            _layout("tavern_1", "tavern"),
            _layout("temple_1", "temple"),
        ])
        like = catalog.matching_allowed(
            catalog.layouts, [BuildingPurposeFamily.TRADE], "like",
        )
        self.assertEqual([row.system_name for row in like], ["tavern_1"])

    def test_omit_packs_is_fantasy(self) -> None:
        enabled = purposes_for_world(None)
        self.assertIn(BuildingPurpose.TAVERN, enabled)
        self.assertIn(BuildingPurpose.HOUSE, enabled)
        self.assertIn(BuildingPurpose.PRISON, enabled)
        self.assertIn(BuildingPurpose.PALACE, enabled)
        self.assertIn(BuildingPurpose.CHANCERY, enabled)
        self.assertIn(BuildingPurpose.ACADEMY, enabled)
        self.assertNotIn(BuildingPurpose.HYPERMARKET, enabled)
        self.assertNotIn(BuildingPurpose.PORTAL, enabled)
        self.assertNotIn(BuildingPurpose.CAFE, enabled)
        self.assertNotIn(BuildingPurpose.LABORATORY, enabled)
        self.assertNotIn(BuildingPurpose.ARCANE_LAB, enabled)
        self.assertEqual(
            WorldPurposePacks.canonical_defaults().root,
            [PurposePack.FANTASY],
        )

    def test_steampunk_magic_union(self) -> None:
        enabled = purposes_for_world(["steampunk", "magic"])
        self.assertIn(BuildingPurpose.PORTAL, enabled)
        self.assertIn(BuildingPurpose.ASSEMBLY_PLANT, enabled)
        self.assertIn(BuildingPurpose.SMITHY, enabled)
        self.assertIn(BuildingPurpose.ARCANE_LAB, enabled)
        self.assertIn(BuildingPurpose.LABORATORY, enabled)
        self.assertIn(BuildingPurpose.ACADEMY, enabled)
        self.assertNotIn(BuildingPurpose.HYPERMARKET, enabled)
        self.assertNotIn(BuildingPurpose.HOUSE, enabled)

    def test_unknown_pack_dropped(self) -> None:
        enabled = purposes_for_world(["fantasy", "nope"])
        self.assertIn(BuildingPurpose.TAVERN, enabled)
        self.assertNotIn(BuildingPurpose.PORTAL, enabled)

    def test_world_row_omit_and_mix(self) -> None:
        empty = SimpleNamespace(world_uid="w1")
        self.assertEqual(purpose_packs(empty).root, [PurposePack.FANTASY])
        self.assertNotIn(
            BuildingPurpose.HYPERMARKET,
            enabled_building_purposes(empty),
        )
        mixed = SimpleNamespace(
            world_uid="w1",
            purpose_packs=["steampunk", "magic"],
        )
        live = enabled_building_purposes(mixed)
        self.assertIn(BuildingPurpose.PORTAL, live)
        self.assertIn(BuildingPurpose.ASSEMBLY_PLANT, live)

    def test_fill_intersect_enabled(self) -> None:
        catalog_types = ("tavern", "hypermarket", "portal", "house")
        fantasy = purposes_for_world(None)
        self.assertEqual(
            allowed_fill_structure_types(None, catalog_types, fantasy),
            ("house", "tavern"),
        )
        self.assertFalse(
            district_hosts_purpose(None, "hypermarket", fantasy),
        )
        leftover = unhosted_settlement_types(
            ["tavern", "portal"],
            [None],
            fantasy,
        )
        self.assertEqual(leftover, ("portal",))

    def test_coerce_allowed_keeps_family(self) -> None:
        self.assertEqual(
            coerce_allowed_list(["trade", "temple", "trade"]),
            [BuildingPurposeFamily.TRADE, BuildingPurpose.TEMPLE],
        )
        self.assertEqual(coerce_allowed_list([]), [])
        self.assertEqual(
            coerce_purpose_list(["trade"], empty_as_house=True),
            [BuildingPurpose.HOUSE],
        )


if __name__ == "__main__":
    unittest.main()
