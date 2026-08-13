"""Wave D leftover: L0 compose has no outdoor grade contributors (R36u-T-8)."""

from __future__ import annotations

import unittest

from app.application.worldData.pack.bake.lightGrid.maskDomainRegistry import (
    build_default_contributors,
)
from app.dataModel.masks.enums.maskDomainId import (
    COMPOSE_CONTRIBUTOR_ORDER,
    LightContributorId,
)


class ComposeOrderWaveDTest(unittest.TestCase):
    def test_grade_contributors_removed_from_l0_compose(self) -> None:
        values = {cid.value for cid in LightContributorId}
        self.assertNotIn("open_land", values)
        self.assertNotIn("shore", values)
        self.assertNotIn("road_shoulder", values)
        order = list(COMPOSE_CONTRIBUTOR_ORDER)
        self.assertLess(
            order.index(LightContributorId.HYDRO),
            order.index(LightContributorId.SETTLEMENT),
        )
        self.assertLess(
            order.index(LightContributorId.SETTLEMENT),
            order.index(LightContributorId.ROAD),
        )
        names = tuple(c.name for c in build_default_contributors())
        self.assertEqual(names, tuple(cid.value for cid in COMPOSE_CONTRIBUTOR_ORDER))


if __name__ == "__main__":
    unittest.main()
