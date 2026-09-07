"""Settlement size rank fallback — medium + json_validation WARNING."""

from __future__ import annotations

import unittest

from app.application.jsonValidation import settlementSizeResolve as _size_resolve
from app.application.jsonValidation.settlementSizeResolve import resolve_settlement_size_key
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
    WorldSettlementSizeRegistry,
)


class TestSettlementSizeResolve(unittest.TestCase):
    def setUp(self) -> None:
        _size_resolve._warned.clear()
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

    def test_unknown_and_non_str_use_medium_and_warn(self) -> None:
        log = "app.application.jsonValidation.settlementSizeResolve"
        with self.assertLogs(log, level="WARNING") as captured:
            self.assertEqual(
                resolve_settlement_size_key(self.sizes, "hamlet", world_uid="w1"),
                self.medium,
            )
            self.assertEqual(
                resolve_settlement_size_key(self.sizes, 12, world_uid="w1"),
                self.medium,
            )
        text = "\n".join(captured.output)
        self.assertIn("settlement_size invalid", text)
        self.assertIn("using field default", text)


if __name__ == "__main__":
    unittest.main()
