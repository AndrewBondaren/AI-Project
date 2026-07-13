"""MERGE-8: LRU decode cache for fine terrain chunks."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.read.fineTerrainDecodeCache import FineTerrainDecodeCache
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun
from app.dataModel.worldPack.packReadPolicy import PackReadPolicy


def _chunk(cx: int, cy: int) -> FineTerrainChunkWire:
    return FineTerrainChunkWire(
        cx=cx,
        cy=cy,
        chunk_columns=32,
        columns=[
            FineTerrainColumnWire(
                lx=0,
                ly=0,
                runs=[FineTerrainZRun(z0=0, z1=0, system_terrain="plains", system_material="soil")],
            ),
        ],
    )


class TestFineTerrainDecodeCache(unittest.TestCase):

    def test_lru_evicts_oldest_wilderness_chunk(self):
        cache = FineTerrainDecodeCache(PackReadPolicy(wilderness_chunk_lru_capacity=1, location_terrain_lru_capacity=1))
        loads = {"a": 0, "b": 0}

        def load_a() -> FineTerrainChunkWire:
            loads["a"] += 1
            return _chunk(0, 0)

        def load_b() -> FineTerrainChunkWire:
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
            writer.write_wilderness_chunk(0, 0, _chunk(0, 0))
            writer.write_wilderness_chunk(0, 0, _chunk(1, 0))
            writer.save_manifest()

            from types import SimpleNamespace

            world = SimpleNamespace(world_uid="w1", terrain_pack_path=None)
            ctx = PackReadContext("w1", db_path=db_path, read_policy=PackReadPolicy(wilderness_chunk_lru_capacity=8, location_terrain_lru_capacity=4))
            reader = ctx.reader_for(world)

            with patch.object(WorldPackReader, "_decode_file", wraps=reader._decode_file) as decode:
                reader.read_wilderness_chunk(0, 0, 0, 0)
                reader.read_wilderness_chunk(0, 0, 0, 0)
                reader.read_wilderness_chunk(0, 0, 1, 0)
                reader.read_wilderness_chunk(0, 0, 0, 0)
            self.assertEqual(decode.call_count, 2)


if __name__ == "__main__":
    unittest.main()
