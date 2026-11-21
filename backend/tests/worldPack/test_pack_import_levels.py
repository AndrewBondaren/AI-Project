"""Import level validation tests."""

import unittest

from app.application.worldData.pack.import_.importLevels import (
    filter_bundle_for_export,
    validate_bundle_for_import,
)


class TestImportLevels(unittest.TestCase):

    def test_registry_export_filter(self):
        bundle = {"world": {}, "races": [], "locations": []}
        out = filter_bundle_for_export(bundle, "registry")
        self.assertEqual(list(out.keys()), ["world"])

    def test_skeleton_rejects_map_cells(self):
        with self.assertRaises(ValueError):
            validate_bundle_for_import({"world": {}, "map_cells": []}, "skeleton")


if __name__ == "__main__":
    unittest.main()
