"""Settlement size rank fallback — medium + json_validation WARNING."""

from __future__ import annotations

import unittest

from app.application.jsonValidation.resolve import UnresolvedModelError
from app.application.jsonValidation.settlementSizeResolve import resolve_settlement_size_key
from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import (
    WorldSettlementSizeRegistry,
)


class TestSettlementSizeResolve(unittest.TestCase):
    def setUp(self) -> None:
        self.sizes = WorldSettlementSizeRegistry.canonical_defaults()
        self.medium = WorldSettlementSizeRegistry.default_system_size()

    def test_omit_is_medium_without_warning(self) -> None:
        with self.assertNoLogs(
            "app.application.jsonValidation.settlementSizeResolve",
            level="WARNING",
        ):
            self.assertEqual(resolve_settlement_size_key(self.sizes, None), self.medium)
            self.assertEqual(resolve_settlement_size_key(self.sizes, ""), self.medium)
            self.assertEqual(resolve_settlement_size_key(self.sizes, "  "), self.medium)

    def test_known_rank_passthrough(self) -> None:
        small = self.sizes.root[0].system_size
        self.assertEqual(resolve_settlement_size_key(self.sizes, small), small)

    def test_unknown_and_non_str_reject_without_medium(self):
        for raw in ("hamlet", 12):
            with self.subTest(raw=raw), self.assertRaises(UnresolvedModelError) as caught:
                resolve_settlement_size_key(self.sizes, raw, world_uid="w1")
            self.assertEqual(caught.exception.path[-1], "system_city_size")


if __name__ == "__main__":
    unittest.main()
