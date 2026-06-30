"""Unit tests for bundleRemapService — BUNDLE-1."""

import unittest

from app.application.worldData.bundleRemapService import remap_bundle


def _minimal_bundle() -> dict:
    return {
        "world": {"world_uid": "w-old", "name": "Test World"},
        "locations": [{
            "location_uid": "loc-1",
            "world_uid": "w-old",
            "parent_location_uid": None,
            "state_uid": "st-1",
        }],
        "states": [{"state_uid": "st-1", "world_uid": "w-old"}],
        "connection_nodes": [{
            "node_uid": "n-1",
            "world_uid": "w-old",
            "location_uid": "loc-1",
        }],
        "connection_edges": [{
            "edge_uid": "e-1",
            "from_node_uid": "n-1",
            "to_node_uid": "n-1",
            "world_uid": "w-old",
            "location_uid": "draft-only",
        }],
        "map_cells": [{
            "world_uid": "w-old",
            "x": 0, "y": 0, "z": 0,
            "location_uid": "loc-1",
        }],
    }


class TestBundleRemap(unittest.TestCase):

    def test_remaps_uids_and_preserves_fk(self):
        src = _minimal_bundle()
        out = remap_bundle(src, 2, lambda n: n)

        self.assertNotEqual(out["world"]["world_uid"], "w-old")
        self.assertEqual(out["world"]["name"], "Test World v2")

        new_w = out["world"]["world_uid"]
        loc = out["locations"][0]
        self.assertEqual(loc["world_uid"], new_w)
        self.assertNotEqual(loc["location_uid"], "loc-1")
        self.assertEqual(loc["state_uid"], out["states"][0]["state_uid"])

        node = out["connection_nodes"][0]
        self.assertEqual(node["location_uid"], loc["location_uid"])

        edge = out["connection_edges"][0]
        self.assertEqual(edge["from_node_uid"], node["node_uid"])
        self.assertNotIn("location_uid", edge)

        cell = out["map_cells"][0]
        self.assertEqual(cell["world_uid"], new_w)
        self.assertEqual(cell["location_uid"], loc["location_uid"])

        # Source unchanged
        self.assertEqual(src["world"]["world_uid"], "w-old")


if __name__ == "__main__":
    unittest.main()
