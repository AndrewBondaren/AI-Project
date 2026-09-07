"""LOC-T-2: settlement size rank vs morphology; footprint = subtype × rank."""

from __future__ import annotations

import unittest

from app.dataModel.locations.locationType.locationTypeSubtypeEntry import LocationTypeSubtypeEntry
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.settlement.settlement.settlementFootprint import (
    SettlementFootprintError,
    resolve_settlement_footprint_multiplier,
    settlement_size_registry_issues,
    village_city_footprint_invariant_holds,
)
from app.dataModel.settlement.settlement.settlementSizeEntry import SettlementSizeEntry
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
    WorldSettlementSizeRegistry,
)


class TestSettlementSizePojo(unittest.TestCase):
    def test_size_entry_has_no_metre_fields(self) -> None:
        fields = set(SettlementSizeEntry.model_fields)
        self.assertEqual(fields, {"system_size", "display_size"})

    def test_canonical_ranks_and_omit_default(self) -> None:
        canon = WorldSettlementSizeRegistry.canonical_defaults()
        self.assertEqual(
            [e.system_size for e in canon.root],
            [
                canon.root[0].system_size,
                WorldSettlementSizeRegistry.default_system_size(),
                canon.root[-1].system_size,
            ],
        )
        self.assertEqual(canon.rank(None), 1)
        self.assertEqual(canon.rank(""), 1)
        self.assertEqual(canon.rank("nope"), -1)


class TestSettlementFootprintHelper(unittest.TestCase):
    def setUp(self) -> None:
        self.types = WorldLocationTypeRegistry.canonical_engine()
        self.sizes = WorldSettlementSizeRegistry.canonical_defaults()
        self.small = self.sizes.root[0].system_size
        self.medium = WorldSettlementSizeRegistry.default_system_size()
        self.large = self.sizes.root[-1].system_size
        settlement = self.types.entry_for(WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT)
        assert settlement is not None
        self.city = next(
            s.system_subtype for s in settlement.subtypes
            if s.required_structure_types
        )
        self.village = next(
            s.system_subtype for s in settlement.subtypes
            if s.l0_map_symbol == "n"
        )

    def test_city_small_exceeds_village_large(self) -> None:
        city_small = resolve_settlement_footprint_multiplier(
            self.city, self.small, self.types, self.sizes,
        )
        village_large = resolve_settlement_footprint_multiplier(
            self.village, self.large, self.types, self.sizes,
        )
        self.assertGreater(city_small, village_large)
        self.assertTrue(village_city_footprint_invariant_holds(self.types, self.sizes))

    def test_omit_size_uses_canonical_medium(self) -> None:
        omitted = resolve_settlement_footprint_multiplier(
            self.city, None, self.types, self.sizes,
        )
        explicit = resolve_settlement_footprint_multiplier(
            self.city, self.medium, self.types, self.sizes,
        )
        self.assertEqual(omitted, explicit)

    def test_unknown_rank_uses_medium(self) -> None:
        unknown = resolve_settlement_footprint_multiplier(
            self.city, "nope", self.types, self.sizes,
        )
        medium = resolve_settlement_footprint_multiplier(
            self.city, self.medium, self.types, self.sizes,
        )
        self.assertEqual(unknown, medium)

    def test_village_plus_village_errors(self) -> None:
        with self.assertRaises(SettlementFootprintError) as ctx:
            resolve_settlement_footprint_multiplier(
                self.village, self.village, self.types, self.sizes,
            )
        self.assertEqual(ctx.exception.code, "DUPLICATE_VALUE")

    def test_morphology_key_in_size_registry_is_issue(self) -> None:
        broken = WorldSettlementSizeRegistry([
            *self.sizes.root,
            SettlementSizeEntry(system_size=self.village, display_size="Dup"),
        ])
        codes = {code for code, _ in settlement_size_registry_issues(self.types, broken)}
        self.assertIn("SIZE_KEY_IS_MORPHOLOGY", codes)

    def test_n1_table_breaking_invariant_is_issue(self) -> None:
        settlement = self.types.entry_for(WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT)
        assert settlement is not None
        overlay_subs = []
        for sub in settlement.subtypes:
            table = dict(sub.footprint_by_size)
            if sub.system_subtype == self.village:
                table[self.large] = 10.0
            overlay_subs.append(
                LocationTypeSubtypeEntry(
                    system_subtype=sub.system_subtype,
                    footprint_by_size=table,
                ),
            )
        world_types = WorldLocationTypeRegistry([
            type(settlement)(
                system_type=settlement.system_type,
                display_type=settlement.display_type,
                parent_types=list(settlement.parent_types),
                is_outdoor=settlement.is_outdoor,
                subtypes=overlay_subs,
            ),
        ]).merged_with_engine()
        self.assertFalse(village_city_footprint_invariant_holds(world_types, self.sizes))
        codes = {code for code, _ in settlement_size_registry_issues(world_types, self.sizes)}
        self.assertIn("VILLAGE_CITY_FOOTPRINT", codes)


if __name__ == "__main__":
    unittest.main()
