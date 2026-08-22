"""Unit tests for per-world generation log sink."""

from __future__ import annotations

import json
import logging
import tempfile
import unittest
from pathlib import Path

from app.core.generationLogging import generation_world_log


class GenerationWorldLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "generation"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_generation_world_log_writes_bake_files(self) -> None:
        logging.getLogger().setLevel(logging.DEBUG)
        pack_log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")
        relief_log = logging.getLogger("app.relief")
        http_log = logging.getLogger("http")
        pack_log.setLevel(logging.DEBUG)
        relief_log.setLevel(logging.DEBUG)

        with generation_world_log(
            "world-terrain-test-001", mode="light", root=self.root,
        ) as run_path:
            pack_log.info("pack surface context | world=world-terrain-test-001 ok=True")
            relief_log.warning("relief | road_shoulder_skip | why='clearance_L_eff'")
            http_log.info("request_end should not appear in generation file")

        self.assertTrue(run_path.is_file())
        latest = self.root / "world-terrain-test-001" / "bake-light-latest.log"
        self.assertTrue(latest.is_file())

        lines = [
            json.loads(line)
            for line in run_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        msgs = [row["msg"] for row in lines]
        self.assertTrue(any("generation log open" in m for m in msgs))
        self.assertTrue(any("pack surface context" in m for m in msgs))
        self.assertTrue(any("road_shoulder_skip" in m for m in msgs))
        self.assertTrue(any("generation log close" in m for m in msgs))
        self.assertFalse(any("request_end" in m for m in msgs))

    def test_generation_world_log_isolates_worlds(self) -> None:
        pack_log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")

        with generation_world_log("world-a", mode="light", root=self.root):
            pack_log.info("only-a")
        with generation_world_log("world-b", mode="light", root=self.root):
            pack_log.info("only-b")

        a_text = (self.root / "world-a" / "bake-light-latest.log").read_text(encoding="utf-8")
        b_text = (self.root / "world-b" / "bake-light-latest.log").read_text(encoding="utf-8")
        self.assertIn("only-a", a_text)
        self.assertNotIn("only-b", a_text)
        self.assertIn("only-b", b_text)
        self.assertNotIn("only-a", b_text)

    def test_generation_world_log_writes_detailed_files(self) -> None:
        logging.getLogger().setLevel(logging.DEBUG)
        pack_log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")
        pack_log.setLevel(logging.DEBUG)

        with generation_world_log(
            "world-terrain-test-001", mode="detailed", root=self.root,
        ) as run_path:
            from app.application.worldData.pack.bake.packBakeLog import (
                log_pack_detailed_bake_done,
                log_pack_l2_formation_done,
            )

            log_pack_l2_formation_done(
                "world-terrain-test-001",
                phase="detailed",
                chunks=1024,
                materialize_s=12.5,
                grade_s=80.25,
                l2_s=42.0,
                tile_gx=-2,
                tile_gy=-2,
                workers=8,
            )
            log_pack_detailed_bake_done(
                "world-terrain-test-001",
                scope="wilderness",
                tiles=1,
                chunks=1024,
                materialize_s=12.5,
                grade_s=80.25,
                l2_s=42.0,
                grade_persist_s=1.5,
            )

        self.assertTrue(run_path.is_file())
        latest = self.root / "world-terrain-test-001" / "bake-detailed-latest.log"
        self.assertTrue(latest.is_file())
        text = latest.read_text(encoding="utf-8")
        self.assertIn("pack l2 formation done", text)
        self.assertIn("grade_s=80.25", text)
        self.assertIn("materialize_s=12.50", text)
        self.assertIn("l2_s=42.00", text)
        self.assertIn("pack detailed_bake done", text)
        self.assertIn("grade_persist_s=1.50", text)
        self.assertIn("bake-detailed-", run_path.name)

    def test_generation_world_log_captures_dump_render_logger(self) -> None:
        logging.getLogger().setLevel(logging.DEBUG)
        dump_log = logging.getLogger("app.application.worldData.render.dumpLog")
        dump_log.setLevel(logging.DEBUG)

        with generation_world_log(
            "world-terrain-test-001", mode="dump", root=self.root,
        ) as run_path:
            dump_log.info(
                "dump grade_z tick",
                extra={"activity": "dump_grade_z", "n": 12},
            )

        self.assertTrue(run_path.is_file())
        latest = self.root / "world-terrain-test-001" / "bake-dump-latest.log"
        self.assertTrue(latest.is_file())
        text = latest.read_text(encoding="utf-8")
        self.assertIn("dump grade_z tick", text)
        self.assertIn("bake-dump-", run_path.name)
        self.assertNotIn("request_end", text)


if __name__ == "__main__":
    unittest.main()
