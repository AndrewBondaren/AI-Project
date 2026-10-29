"""Cache invalidation follows exact GEO dependencies across the consumption seam."""

from unittest import TestCase
from unittest.mock import patch

from tests.geo1.integration.support.fixtures import Seam


class SeamRevisionTests(TestCase):
    def setUp(self):
        self.seam = Seam()
        self.addCleanup(self.seam.service.shutdown)

    def test_warm_cache_skips_all_three_builds_and_final_edit_invalidates(self):
        first = self.seam.run(self.seam.final(source="before"))
        with patch.object(self.seam.registry, "build", wraps=self.seam.registry.build) as builds:
            self.assertEqual(self.seam.run(self.seam.final(source="before")), first)
            builds.assert_not_called()
            second = self.seam.run(self.seam.final(source="after"))
            self.assertEqual(builds.call_count, 3)
        for name in ("climate_local", "surface_support", "coating"):
            self.assertNotEqual(first[name].ref.key, second[name].ref.key)
        for name in ("climate_base", "terrain_base"):
            self.assertEqual(first[name].ref, second[name].ref)

    def test_new_service_replays_the_same_refs(self):
        expected = self.seam.run(self.seam.final())
        other = Seam()
        self.addCleanup(other.service.shutdown)
        self.assertEqual(expected, other.run(other.final()))
