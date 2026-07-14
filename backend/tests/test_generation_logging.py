"""Unit tests for per-world generation log sink."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.generationLogging import generation_world_log


def test_generation_world_log_writes_bake_files(tmp_path: Path) -> None:
    root = tmp_path / "generation"
    pack_log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")
    http_log = logging.getLogger("http")

    with generation_world_log("world-terrain-test-001", mode="light", root=root) as run_path:
        pack_log.info("pack surface context | world=world-terrain-test-001 ok=True")
        http_log.info("request_end should not appear in generation file")

    assert run_path.is_file()
    latest = root / "world-terrain-test-001" / "bake-light-latest.log"
    assert latest.is_file()

    lines = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    msgs = [row["msg"] for row in lines]
    assert any("generation log open" in m for m in msgs)
    assert any("pack surface context" in m for m in msgs)
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
