"""S4: default material policy helper — RICH → max, all other bands → min."""
import unittest

from app.application.economy.materialPolicies.defaultMaterialPolicy import (
    default_material_policy,
)
from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.dataModel.economy.materialPolicies import (
    BuildingEconomicContext, MaterialPolicy,
)


def context(tier, band):
    return BuildingEconomicContext(economic_tier=tier, band=band)


class DefaultMaterialPolicyTests(unittest.TestCase):
    def test_rich_selects_max_strength_all_other_bands_min(self):
        self.assertEqual(
            default_material_policy(context("exceptional", EconomicTierBand.RICH)),
            MaterialPolicy.MAX_STRENGTH)
        for band in (EconomicTierBand.POOR, EconomicTierBand.COMMON,
                     EconomicTierBand.MIDDLE, EconomicTierBand.WEALTHY):
            with self.subTest(band=band):
                self.assertEqual(
                    default_material_policy(context("basic", band)),
                    MaterialPolicy.MIN_STRENGTH)

    def test_wealthy_is_not_rich(self):
        self.assertEqual(
            default_material_policy(context("quality", EconomicTierBand.WEALTHY)),
            MaterialPolicy.MIN_STRENGTH)
        self.assertEqual(
            default_material_policy(context("quality", EconomicTierBand.RICH)),
            MaterialPolicy.MAX_STRENGTH)

    def test_tier_name_never_matters_only_band(self):
        for tier in ("premium", "exceptional", "custom_gold", "whatever"):
            with self.subTest(tier=tier):
                self.assertEqual(
                    default_material_policy(context(tier, EconomicTierBand.RICH)),
                    MaterialPolicy.MAX_STRENGTH)
                self.assertEqual(
                    default_material_policy(context(tier, EconomicTierBand.COMMON)),
                    MaterialPolicy.MIN_STRENGTH)

    def test_existing_band_mapping_drives_rule_at_any_registry_size(self):
        # §3 mapping on arbitrary registry names: N=1 → middle, N=2 → poor/rich.
        for n in (1, 2, 3, 6, 7):
            tiers = [f"tier_{i}" for i in range(n)]
            band_map = EconomicTierBand.band_map_for_sorted_tiers(tiers)
            for tier, wire_band in band_map.items():
                band = EconomicTierBand.from_wire(wire_band)
                expected = (MaterialPolicy.MAX_STRENGTH
                            if band == EconomicTierBand.RICH
                            else MaterialPolicy.MIN_STRENGTH)
                with self.subTest(n=n, tier=tier, band=band):
                    self.assertEqual(
                        default_material_policy(context(tier, band)), expected)
