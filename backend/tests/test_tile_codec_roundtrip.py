"""TileCodec roundtrip tests."""

import tempfile
import unittest
from pathlib import Path

from app.application.worldData.pack.tileCodec import (
    PAYLOAD_KIND_L0,
    PAYLOAD_KIND_L2,
    TileCodec,
)


class TestTileCodecRoundtrip(unittest.TestCase):

    def setUp(self) -> None:
        self.codec = TileCodec()

    def test_roundtrip_stable_hash(self):
        payload = {"cells_per_side": 2, "cells": [{"tx": 0, "ty": 0, "surface_z": 10}]}
        blob_a = self.codec.encode(PAYLOAD_KIND_L0, payload)
        blob_b = self.codec.encode(PAYLOAD_KIND_L0, payload)
        self.assertEqual(self.codec.content_hash(blob_a), self.codec.content_hash(blob_b))
        kind, restored = self.codec.decode(blob_a)
        self.assertEqual(kind, PAYLOAD_KIND_L0)
        self.assertEqual(restored["cells_per_side"], 2)

    def test_l2_kind(self):
        payload = {"cx": 0, "cy": 0, "chunk_columns": 32, "columns": []}
        blob = self.codec.encode(PAYLOAD_KIND_L2, payload)
        kind, restored = self.codec.decode(blob)
        self.assertEqual(kind, PAYLOAD_KIND_L2)
        self.assertEqual(restored["chunk_columns"], 32)

    def test_tmp_not_left_on_atomic_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tile.zst"
            blob = self.codec.encode(PAYLOAD_KIND_L0, {"cells_per_side": 1, "cells": []})
            tmp_path = target.with_suffix(target.suffix + ".tmp")
            tmp_path.write_bytes(blob)
            tmp_path.replace(target)
            self.assertTrue(target.is_file())
            self.assertFalse(tmp_path.exists())


if __name__ == "__main__":
    unittest.main()
