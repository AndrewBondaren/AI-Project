"""Route tests for ``loggingConfig`` domain/service files — ``docs/tz_logging.md``."""

from __future__ import annotations

from app.core.logging.contracts import LogConsumer
import io
import json
import logging
import queue
import threading
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
    set_logging_level,
    setup_logging,
)
from app.core.logging.routes import route_for
from app.core.logging.contracts import LogSink, UnknownLogConsumerError
from app.application.worldData.generators.terrain.relief.log.log import relief_error
from app.core.logging.console import flush_console_queue


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
    def test_formatter_preserves_factory_extras_and_traceback(self) -> None:
        import importlib
        import sys
        from app.core.logging import formatting

        previous_factory = logging.getLogRecordFactory()

        def factory(*args, **kwargs):
            record = previous_factory(*args, **kwargs)
            record.correlation_token = "domain-correlation"
            return record

        try:
            logging.setLogRecordFactory(factory)
            importlib.reload(formatting)
            try:
                raise OSError("source failure")
            except OSError:
                record = logging.getLogger("factory.probe").makeRecord(
                    "factory.probe", logging.ERROR, __file__, 1, "failed %s", ("operation",),
                    sys.exc_info(), extra={"failure": {"code": "io_error"}},
                )
            # Another handler may already have formatted this same record.
            logging.Formatter("%(asctime)s %(message)s").format(record)
            data = json.loads(formatting.JsonLogFormatter().format(record))
            self.assertEqual(set(data), {"ts", "level", "logger", "request_id", "msg",
                                         "correlation_token", "failure", "exc"})
            self.assertEqual(data["msg"], "failed operation")
            self.assertEqual(data["correlation_token"], "domain-correlation")
            self.assertEqual(data["failure"], {"code": "io_error"})
            self.assertIn("OSError: source failure", data["exc"])
        finally:
            logging.setLogRecordFactory(previous_factory)
            importlib.reload(formatting)

    def test_default_log_root_and_shared_request_context(self) -> None:
        from app.core.logging.fileRouter import backend_logs_dir, consumer_log_path
        from app.core.logging.formatting import JsonLogFormatter
        from app.core.logging.context import request_id_var
        from app.core import logMiddleware

        expected = Path(__file__).resolve().parents[1] / "logs"
        self.assertEqual(backend_logs_dir(), expected)
        self.assertEqual(consumer_log_path(LogSink.TIME_OPERATIONS), expected / "time" / "operations.log")
        before = request_id_var.get()
        token = logMiddleware.request_id_var.set("shared-request")
        record = logging.LogRecord("probe", logging.INFO, __file__, 1, "probe", (), None)
        try:
            self.assertEqual(json.loads(JsonLogFormatter().format(record))["request_id"], "shared-request")
        finally:
            logMiddleware.request_id_var.reset(token)
        self.assertEqual(json.loads(JsonLogFormatter().format(record))["request_id"], before)

    def test_full_console_queue_drops_without_blocking(self) -> None:
        from app.core.logging.console import _DropQueueHandler

        pending = queue.Queue(maxsize=1)
        record = logging.LogRecord("probe", logging.INFO, __file__, 1, "probe", (), None)
        pending.put_nowait(record)
        handler = _DropQueueHandler(pending)
        worker = threading.Thread(target=handler.enqueue, args=(record,), daemon=True)
        worker.start()
        worker.join(timeout=1)
        blocked = worker.is_alive()
        try:
            self.assertFalse(blocked)
            self.assertEqual(pending.qsize(), 1)
        finally:
            if blocked:
                pending.get_nowait()
                worker.join(timeout=1)
            handler.close()

    def test_http_and_relief_split(self) -> None:
        self.assertIs(route_for("http.access").sink, LogSink.HTTP)
        self.assertIs(route_for("app.relief.rays").sink, LogSink.RELIEF_RAYS)
        self.assertIs(route_for("uvicorn.error").sink, LogSink.CORE_RUNTIME)
        self.assertIs(route_for("httpx").sink, LogSink.CORE_RUNTIME)
        with self.assertRaises(UnknownLogConsumerError):
            route_for("httpOther")


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
    def test_reconfigure_preserves_transcript_and_stops_old_listener(self) -> None:
        from app.core.logging import console

        self._install_server()
        assert console._console_listener is not None
        old_thread = console._console_listener._thread
        assert old_thread is not None
        with generation_world_log("reconfigure", mode="light", root=self.logs / "generation") as transcript:
            logging.getLogger("app.artifacts").warning("before")
            self._install_server()
            self.assertFalse(old_thread.is_alive())
            logging.getLogger("app.artifacts").warning("after")
            _flush_facade()
            self.assertEqual(_read_json_msgs(self.logs / "artifacts" / "artifactLifecycle.log"), ["before", "after"])
        messages = _read_json_msgs(transcript)
        self.assertEqual(messages.count("before"), 1)
        self.assertEqual(messages.count("after"), 1)
        assert console._console_listener is not None
        current_thread = console._console_listener._thread
        assert current_thread is not None
        _remove_facade_handlers()
        self.assertFalse(current_thread.is_alive())

    def test_time_emitter_server_route_and_filtering(self) -> None:
        from app.application.time.logging.timeOperationLog import TimeOperationLog
        from app.dataModel.time.diagnostics.events import CurrentLogContext
        from app.core.logging.context import request_id_var
        from tests.time.test_time_core import publication

        self._install_server()
        self.assertIs(route_for("app.time.operations").sink, LogSink.TIME_OPERATIONS)
        producer = TimeOperationLog()
        context = CurrentLogContext(expected=publication())
        token = request_id_var.set("time-route")
        try:
            with generation_world_log("world", mode="light", root=self.logs / "generation") as transcript:
                producer.emit_cancelled(context)
                set_logging_level(logging.INFO)
                producer.emit_cancelled(context)
                producer.emit_fault(context)
            _flush_facade()
        finally:
            request_id_var.reset(token)
        rows = [json.loads(line) for line in (self.logs / "time" / "operations.log").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["activity"] for row in rows], ["operation_cancelled", "operation_failed"])
        self.assertTrue(all(row["request_id"] == "time-route" for row in rows))
        self.assertTrue(all(row["publication_id"] == "publication" for row in rows))
        runtime = self.logs / "core" / "runtime.log"
        if runtime.exists():
            self.assertNotIn("app.time.operations", runtime.read_text(encoding="utf-8"))
        self.assertNotIn("app.time.operations", transcript.read_text(encoding="utf-8"))

    def test_time_emitter_preserves_script_profile(self) -> None:
        from app.application.time.logging.timeOperationLog import TimeOperationLog
        from app.dataModel.time.diagnostics.events import CurrentLogContext
        from tests.time.test_time_core import publication

        self._install_script()
        TimeOperationLog().emit_fault(CurrentLogContext(expected=publication()))
        _flush_facade()
        self.assertEqual(_read_json_msgs(self.logs / "script" / "detailedBake.log"), ["operation_failed"])
        self.assertFalse((self.logs / "time" / "operations.log").exists())

    def test_artifacts_route_preserves_traceback_in_domain_file_and_transcript(self) -> None:
        self._install_server()
        self.assertIs(route_for("app.artifacts").sink, LogSink.ARTIFACTS)
        with generation_world_log("artifact-world", mode="light", root=self.logs / "generation") as run_path:
            try:
                raise OSError("artifact route probe")
            except OSError:
                logging.getLogger("app.artifacts").exception(
                    "artifact failure probe", extra={"operation_id": "maintenance-probe", "world_uid": None})
        _flush_facade()
        domain = self.logs / "artifacts" / "artifactLifecycle.log"
        rows = [json.loads(line) for line in domain.read_text(encoding="utf-8").splitlines()]
        copies = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines()
                  if json.loads(line).get("msg") == "artifact failure probe"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(copies), 1)
        for record in (rows[0], copies[0]):
            self.assertEqual(record["operation_id"], "maintenance-probe")
            self.assertIsNone(record["world_uid"])
            self.assertIn("artifact route probe", record["exc"])
            self.assertIn("test_artifacts_route_preserves_traceback", record["exc"])
        self.assertEqual(rows[0]["exc"], copies[0]["exc"])

    def test_real_gc_emitter_preserves_failure_in_file_and_transcript(self) -> None:
        from tests.snapshotCore.support.fixtures import run_async
        from unittest.mock import AsyncMock, create_autospec
        from app.application.artifacts.lifecycle.artifactGc import ArtifactGarbageCollector
        from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
        from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
        from tests.snapshotCore.storage.artifacts.test_staging import LifecycleFixture
        from tests.snapshotCore.support.artifactFixtures import descriptor

        self._install_server()
        state = LifecycleFixture()
        ref, next_ref = descriptor("failed"), descriptor("next")
        state.refs.update({ref: ref, next_ref: next_ref})
        registry = create_autospec(ArtifactFormatRegistryBinding, instance=True)
        cause = OSError(5, "GC original failure")

        async def delete(candidate):
            if candidate == ref:
                raise cause

        registry.delete = AsyncMock(side_effect=delete)
        gc = ArtifactGarbageCollector(registry, state, state, ArtifactLifecycleLog())
        with generation_world_log("gc-world", mode="light", root=self.logs / "generation") as transcript:
            report = run_async(gc.collect("gc-operation", (ref, next_ref)))
        self.assertEqual(report.deleted, (next_ref,))
        self.assertEqual(len(report.failed), 1)
        failure = report.failed[0]
        self.assertEqual(failure.ref, ref)
        self.assertEqual(failure.stage.value, "delete")
        _flush_facade()
        paths = (self.logs / "artifacts" / "artifactLifecycle.log", transcript)
        failures = []
        for path in paths:
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            failed = [row for row in rows if row.get("activity") == "gc_failed"]
            self.assertEqual(len(failed), 1)
            self.assertEqual(sum(row.get("activity") == "gc_deleted" for row in rows), 1)
            row = failed[0]
            self.assertEqual(row["operation_id"], "gc-operation")
            self.assertIsNone(row["world_uid"])
            self.assertEqual(row["gc_failure"], failure.model_dump(mode="json", exclude={"message"}))
            self.assertIn('raise cause', row["exc"])
            self.assertIn('in delete', row["exc"])
            self.assertIn(str(cause), row["exc"])
            failures.append(row)
        self.assertEqual(failures[0]["exc"], failures[1]["exc"])

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
        relief_error("grade_cell_empty_ray", x=1, y=2)
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
        logging.getLogger(LogConsumer.RENDER_DUMP.value).info(
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
            relief_error("grade_cell_empty_ray", x=1, y=2)
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
        relief_error("grade_cell_empty_ray", x=1, y=2)
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

    def test_json_validation_writes_resolve_log(self) -> None:
        self._install_server()
        logging.getLogger(LogConsumer.RESOLVE.value).warning(
            "json_validation | settlement_size invalid 'hamlet'; using field default 'medium'",
            extra={"activity": "settlement_size_fallback"},
        )
        _flush_facade()
        path = self.logs / "jsonValidation" / "resolve.log"
        self.assertTrue(path.is_file())
        self.assertTrue(
            any("settlement_size invalid" in m for m in _read_json_msgs(path)),
        )
        self.assertFalse((self.logs / "core" / "runtime.log").exists())

    def test_settlement_assembler_writes_settlement_log(self) -> None:
        self._install_server()
        logging.getLogger(
            LogConsumer.SETTLEMENT_PACKING.value,
        ).info(
            "C22 packing | district=civic_center step=frame",
            extra={"activity": "frame"},
        )
        logging.getLogger(
            LogConsumer.SETTLEMENT_PACKING.value,
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
        relief_error("grade_cell_empty_ray", x=1, y=2)
        logging.getLogger("__main__").info("waiting for bake")
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
        logging.getLogger(LogConsumer.RENDER_DUMP.value).info(
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
        dump = logging.getLogger(LogConsumer.RENDER_DUMP.value)
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
