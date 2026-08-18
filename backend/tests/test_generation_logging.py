"""Unit tests for per-world generation log sink."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.generationLogging import generation_world_log


def test_generation_world_log_writes_bake_files(tmp_path: Path) -> None:
    root = tmp_path / "generation"
    logging.getLogger().setLevel(logging.DEBUG)
    pack_log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")
    relief_log = logging.getLogger("app.relief")
    http_log = logging.getLogger("http")
    pack_log.setLevel(logging.DEBUG)
    relief_log.setLevel(logging.DEBUG)

    with generation_world_log("world-terrain-test-001", mode="light", root=root) as run_path:
        pack_log.info("pack surface context | world=world-terrain-test-001 ok=True")
        relief_log.warning("relief | road_shoulder_skip | why='clearance_L_eff'")
        http_log.info("request_end should not appear in generation file")

    assert run_path.is_file()
    latest = root / "world-terrain-test-001" / "bake-light-latest.log"
    assert latest.is_file()

    lines = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    msgs = [row["msg"] for row in lines]
    assert any("generation log open" in m for m in msgs)
    assert any("pack surface context" in m for m in msgs)
    assert any("road_shoulder_skip" in m for m in msgs)
    assert any("generation log close" in m for m in msgs)
    assert not any("request_end" in m for m in msgs)


def test_generation_world_log_isolates_worlds(tmp_path: Path) -> None:
    root = tmp_path / "generation"
    pack_log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")

    with generation_world_log("world-a", mode="light", root=root):
        pack_log.info("only-a")
    with generation_world_log("world-b", mode="light", root=root):
        pack_log.info("only-b")

    a_text = (root / "world-a" / "bake-light-latest.log").read_text(encoding="utf-8")
    b_text = (root / "world-b" / "bake-light-latest.log").read_text(encoding="utf-8")
    assert "only-a" in a_text and "only-b" not in a_text
    assert "only-b" in b_text and "only-a" not in b_text


def test_generation_world_log_writes_detailed_files(tmp_path: Path) -> None:
    root = tmp_path / "generation"
    logging.getLogger().setLevel(logging.DEBUG)
    pack_log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")
    pack_log.setLevel(logging.DEBUG)

    with generation_world_log("world-terrain-test-001", mode="detailed", root=root) as run_path:
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

    assert run_path.is_file()
    latest = root / "world-terrain-test-001" / "bake-detailed-latest.log"
    assert latest.is_file()
    text = latest.read_text(encoding="utf-8")
    assert "pack l2 formation done" in text
    assert "grade_s=80.25" in text
    assert "materialize_s=12.50" in text
    assert "l2_s=42.00" in text
    assert "pack detailed_bake done" in text
    assert "grade_persist_s=1.50" in text
    assert "bake-detailed-" in run_path.name

