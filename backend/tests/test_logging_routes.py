"""Route tests for ``loggingConfig`` domain/service files — ``docs/tz_logging.md``."""

from __future__ import annotations

import io
import json
import logging
import tempfile
import unittest
from pathlib import Path

from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_grade_ray_validate_start,
)
from app.core.generationLogging import generation_world_log
from app.core.loggingConfig import (
    _remove_facade_handlers,
    ensure_script_logging,
    flush_console_queue,
    route_for,
    set_logging_level,
    setup_logging,
)


def _flush_facade() -> None:
    flush_console_queue()
    for handler in logging.getLogger().handlers:
        handler.flush()


def _read_json_msgs(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [
        json.loads(line)["msg"]
        for line in text.splitlines()
        if line.strip()
    ]


class RouteTableTests(unittest.TestCase):
    def test_http_and_relief_split(self) -> None:
        self.assertEqual(route_for("http"), ("http", "api"))
        self.assertEqual(route_for("http.access"), ("http", "api"))
        self.assertEqual(
            route_for("app.relief", "grade_cell_empty_ray"),
            ("relief", "gradeCellRays"),
        )
        self.assertEqual(
            route_for("app.relief", "road_shoulder_skip"),
            ("relief", "reliefLog"),
        )
        self.assertEqual(route_for("app.relief"), ("relief", "reliefLog"))
        self.assertIsNone(route_for("uvicorn.error"))
        self.assertIsNone(route_for("httpx"))
        self.assertEqual(
            route_for("app.application.worldData.generators.assemblers.districtAssembler"),
            ("settlement", "settlementAssembler"),
        )
        self.assertEqual(
            route_for("app.application.worldData.generators.assemblers.climateAssembler"),
            ("climate", "climateLog"),
        )


class _LogDirCase(unittest.TestCase):
    def setUp(self) -> None:
        _remove_facade_handlers()
        self._tmp = tempfile.TemporaryDirectory()
        self.logs = Path(self._tmp.name)
        self._stream = io.StringIO()

    def tearDown(self) -> None:
        _remove_facade_handlers()
        self._tmp.cleanup()

    def _install_server(self) -> None:
        setup_logging(
            level=logging.DEBUG,
            profile="server",
            logs_dir=self.logs,
            stream=self._stream,
        )

    def _install_script(self, service: str = "detailedBake") -> None:
        setup_logging(
            level=logging.DEBUG,
            profile="script",
            script_service=service,
            logs_dir=self.logs,
            stream=self._stream,
        )


class ServerRouteFileTests(_LogDirCase):
    def test_http_writes_api_log(self) -> None:
        self._install_server()
        logging.getLogger("http").info("request_start method=GET path=/api/worlds")
        _flush_facade()
        path = self.logs / "http" / "api.log"
        self.assertTrue(path.is_file())
        self.assertTrue(any("request_start" in m for m in _read_json_msgs(path)))
        self.assertFalse((self.logs / "app.log").exists())

    def test_relief_r44_writes_grade_cell_rays(self) -> None:
        self._install_server()
        logging.getLogger("app.relief").error(
            "relief | grade_cell_empty_ray | x=1 y=2",
            extra={"activity": "grade_cell_empty_ray"},
        )
        _flush_facade()
        rays = self.logs / "relief" / "gradeCellRays.log"
        relief = self.logs / "relief" / "reliefLog.log"
        self.assertTrue(rays.is_file())
        self.assertTrue(any("grade_cell_empty_ray" in m for m in _read_json_msgs(rays)))
        self.assertFalse(relief.exists())

    def test_other_relief_writes_relief_log(self) -> None:
        self._install_server()
        logging.getLogger("app.relief").warning(
            "relief | road_shoulder_skip | why='clearance_L_eff'",
            extra={"activity": "road_shoulder_skip"},
        )
        _flush_facade()
        relief = self.logs / "relief" / "reliefLog.log"
        rays = self.logs / "relief" / "gradeCellRays.log"
        self.assertTrue(relief.is_file())
        self.assertTrue(any("road_shoulder_skip" in m for m in _read_json_msgs(relief)))
        self.assertFalse(rays.exists())

    def test_unmatched_writes_core_runtime_not_app_log(self) -> None:
        self._install_server()
        logging.getLogger("uvicorn.error").error("boom")
        _flush_facade()
        runtime = self.logs / "core" / "runtime.log"
        self.assertTrue(runtime.is_file())
        self.assertTrue(any("boom" in m for m in _read_json_msgs(runtime)))
        self.assertFalse((self.logs / "app.log").exists())

    def test_server_does_not_open_dump_log(self) -> None:
        self._install_server()
        logging.getLogger("app.application.worldData.render.dumpLog").info(
            "dump tick",
            extra={"activity": "dump"},
        )
        _flush_facade()
        self.assertFalse((self.logs / "render").exists())
        self.assertFalse((self.logs / "script").exists())

    def test_set_logging_level_does_not_open_app_log(self) -> None:
        self._install_server()
        before = list(logging.getLogger().handlers)
        set_logging_level(logging.ERROR)
        self.assertEqual(list(logging.getLogger().handlers), before)
        logging.getLogger("http").info("should-be-filtered")
        _flush_facade()
        self.assertFalse((self.logs / "app.log").exists())
        api = self.logs / "http" / "api.log"
        self.assertFalse(api.exists())

    def test_r44_and_transcript_both_see_relief(self) -> None:
        self._install_server()
        gen_root = self.logs / "generation"
        relief = logging.getLogger("app.relief")
        relief.setLevel(logging.DEBUG)
        with generation_world_log(
            "world-x", mode="detailed", root=gen_root,
        ) as run_path:
            relief.error(
                "relief | grade_cell_empty_ray | x=1 y=2",
                extra={"activity": "grade_cell_empty_ray"},
            )
        _flush_facade()
        self.assertIn(
            "grade_cell_empty_ray",
            run_path.read_text(encoding="utf-8"),
        )
        rays = self.logs / "relief" / "gradeCellRays.log"
        self.assertTrue(rays.is_file())
        self.assertTrue(
            any("grade_cell_empty_ray" in m for m in _read_json_msgs(rays)),
        )
        self.assertNotIn("grade_cell_empty_ray", self._stream.getvalue())

    def test_console_skips_volume_keeps_pack_heartbeat(self) -> None:
        self._install_server()
        logging.getLogger("app.relief").error(
            "relief | grade_cell_empty_ray | x=1 y=2",
            extra={"activity": "grade_cell_empty_ray"},
        )
        logging.getLogger("app.relief").debug(
            "relief | grade_system_create | uid=sys-1",
            extra={"activity": "grade_system_create"},
        )
        log_pack_grade_ray_validate_start("world-x", n_cells=12)
        _flush_facade()
        console = self._stream.getvalue()
        self.assertNotIn("grade_cell_empty_ray", console)
        self.assertNotIn("grade_system_create", console)
        self.assertIn("grade_ray validate start", console)
        rays = self.logs / "relief" / "gradeCellRays.log"
        self.assertTrue(
            any("grade_cell_empty_ray" in m for m in _read_json_msgs(rays)),
        )
        relief = self.logs / "relief" / "reliefLog.log"
        self.assertTrue(
            any("grade_system_create" in m for m in _read_json_msgs(relief)),
        )
        pack = self.logs / "pack" / "packBakeLog.log"
        self.assertTrue(
            any("grade_ray validate start" in m for m in _read_json_msgs(pack)),
        )

    def test_settlement_assembler_writes_settlement_log(self) -> None:
        self._install_server()
        logging.getLogger(
            "app.application.worldData.generators.assemblers",
        ).info(
            "C22 packing | district=civic_center step=frame",
            extra={"activity": "frame"},
        )
        logging.getLogger(
            "app.application.worldData.generators.assemblers",
        ).debug(
            "C22 packing | district=civic_center step=fit fit='no'",
            extra={"activity": "c22_packing_fit"},
        )
        _flush_facade()
        path = self.logs / "settlement" / "settlementAssembler.log"
        self.assertTrue(path.is_file())
        msgs = _read_json_msgs(path)
        self.assertTrue(any("step=frame" in m for m in msgs))
        self.assertTrue(any("step=fit" in m for m in msgs))
        self.assertNotIn("step=fit", self._stream.getvalue())


class ScriptProfileTests(_LogDirCase):
    def test_script_writes_stem_log_not_app_or_relief(self) -> None:
        self._install_script("detailedBake")
        logging.getLogger("http").info("request_end should not create http/api")
        logging.getLogger("app.relief").error(
            "relief | grade_cell_empty_ray | x=0 y=0",
            extra={"activity": "grade_cell_empty_ray"},
        )
        logging.getLogger("poll").info("waiting for bake")
        _flush_facade()
        script_log = self.logs / "script" / "detailedBake.log"
        self.assertTrue(script_log.is_file())
        msgs = _read_json_msgs(script_log)
        self.assertTrue(any("waiting for bake" in m for m in msgs))
        self.assertFalse((self.logs / "app.log").exists())
        self.assertFalse((self.logs / "relief").exists())
        self.assertFalse((self.logs / "pack").exists())
        self.assertFalse((self.logs / "http").exists())

    def test_script_dump_also_opens_dump_log(self) -> None:
        self._install_script("renderMaps")
        logging.getLogger("app.application.worldData.render.dumpLog").info(
            "dump grade_z tick",
            extra={"activity": "dump_grade_z"},
        )
        _flush_facade()
        dump = self.logs / "render" / "dumpLog.log"
        self.assertTrue(dump.is_file())
        self.assertTrue(any("dump grade_z tick" in m for m in _read_json_msgs(dump)))
        self.assertTrue((self.logs / "script" / "renderMaps.log").is_file())
        self.assertFalse((self.logs / "relief").exists())
        self.assertFalse((self.logs / "app.log").exists())

    def test_ensure_script_logging_does_not_create_app_log(self) -> None:
        ensure_script_logging(
            service="lightAndFullBake",
            logs_dir=self.logs,
            stream=self._stream,
        )
        logging.getLogger("app.relief").warning(
            "relief | ribbon_skip_apply",
            extra={"activity": "ribbon_skip_apply"},
        )
        _flush_facade()
        self.assertTrue((self.logs / "script" / "lightAndFullBake.log").is_file())
        self.assertFalse((self.logs / "app.log").exists())
        self.assertFalse((self.logs / "relief").exists())

    def test_transcript_still_captures_relief_and_dump(self) -> None:
        self._install_script("detailedBake")
        gen_root = self.logs / "generation"
        relief = logging.getLogger("app.relief")
        dump = logging.getLogger("app.application.worldData.render.dumpLog")
        relief.setLevel(logging.DEBUG)
        dump.setLevel(logging.DEBUG)
        with generation_world_log("world-x", mode="dump", root=gen_root) as run_path:
            relief.warning(
                "relief | road_shoulder_skip | why='clearance_L_eff'",
                extra={"activity": "road_shoulder_skip"},
            )
            dump.info("dump grade_z tick", extra={"activity": "dump_grade_z", "n": 12})
        text = run_path.read_text(encoding="utf-8")
        self.assertIn("road_shoulder_skip", text)
        self.assertIn("dump grade_z tick", text)
        self.assertFalse((self.logs / "relief").exists())
        self.assertTrue((self.logs / "render" / "dumpLog.log").is_file())


if __name__ == "__main__":
    unittest.main()
