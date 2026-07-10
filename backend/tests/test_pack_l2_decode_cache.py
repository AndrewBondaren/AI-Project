"""MERGE-8: LRU decode cache for L2 chunks."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.packL2DecodeCache import PackL2DecodeCache
from app.application.worldData.pack.packReadContext import PackReadContext
from app.application.worldData.pack.worldPackReader import WorldPackReader
from app.dataModel.worldPack.l2ChunkWire import L2ChunkWire, L2ColumnWire, L2ZRun
from app.dataModel.worldPack.packReadPolicy import PackReadPolicy


def _chunk(cx: int, cy: int) -> L2ChunkWire:
    return L2ChunkWire(
        cx=cx,
        cy=cy,
        chunk_columns=32,
        columns=[
            L2ColumnWire(
                lx=0,
                ly=0,
                runs=[L2ZRun(z0=0, z1=0, system_terrain="plains", system_material="soil")],
            ),
        ],
    )


class TestPackL2DecodeCache(unittest.TestCase):

    def test_lru_evicts_oldest_wilderness_chunk(self):
        cache = PackL2DecodeCache(PackReadPolicy(l2_chunk_lru_capacity=1, location_l2_lru_capacity=1))
        loads = {"a": 0, "b": 0}

        def load_a() -> L2ChunkWire:
            loads["a"] += 1
            return _chunk(0, 0)

        def load_b() -> L2ChunkWire:
            loads["b"] += 1
            return _chunk(1, 0)

        cache.get_wilderness_chunk((0, 0, 0, 0), load_a)
        cache.get_wilderness_chunk((0, 0, 1, 0), load_b)
        self.assertEqual(loads, {"a": 1, "b": 1})
        self.assertEqual(cache.wilderness_chunk_count(), 1)

        cache.get_wilderness_chunk((0, 0, 0, 0), load_a)
        self.assertEqual(loads["a"], 2)

    def test_reader_uses_shared_context_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "game.db")
            paths = WorldPackPaths.from_db_parent(db_path, "w1")
            writer = WorldPackWriter(paths)
            writer.write_l2_wilderness_chunk(0, 0, _chunk(0, 0))
            writer.write_l2_wilderness_chunk(0, 0, _chunk(1, 0))
            writer.save_manifest()

            from types import SimpleNamespace

            world = SimpleNamespace(world_uid="w1", terrain_pack_path=None)
            ctx = PackReadContext("w1", db_path=db_path, read_policy=PackReadPolicy(l2_chunk_lru_capacity=8, location_l2_lru_capacity=4))
            reader = ctx.reader_for(world)

            with patch.object(WorldPackReader, "_decode_file", wraps=reader._decode_file) as decode:
                reader.read_l2_chunk(0, 0, 0, 0)
                reader.read_l2_chunk(0, 0, 0, 0)
                reader.read_l2_chunk(0, 0, 1, 0)
                reader.read_l2_chunk(0, 0, 0, 0)
            self.assertEqual(decode.call_count, 2)


if __name__ == "__main__":
    unittest.main()
