"""Public settings operations through real facade and transcript files."""

import io
import json
import logging
import tempfile
import unittest
from pathlib import Path

from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.physics.settings.input import (
    resolve_world_physics_settings_input_runtime as runtime,
    validate_world_physics_settings_input as validate,
)
from app.core.generationLogging import generation_world_log
from app.core.loggingConfig import (
    _remove_facade_handlers, flush_console_queue, request_id_var, setup_logging, route_for,
)


class SettingsLoggingTests(unittest.TestCase):
    def setUp(self):
        self.level = logging.getLogger().level
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        setup_logging(level=logging.DEBUG, profile="server", logs_dir=self.root, stream=io.StringIO())

    def tearDown(self):
        _remove_facade_handlers()
        logging.getLogger().setLevel(self.level)
        self.tmp.cleanup()

    def rows(self, path):
        flush_console_queue()
        for handler in logging.getLogger().handlers:
            handler.flush()
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def physics(self, path):
        return [row for row in self.rows(path) if row["logger"] == "app.application.physics.settings"]

    def test_sink_transcript_dedup_correlation_and_world_isolation(self):
        self.assertEqual(route_for("app.application.physics.settings"), ("physics", "physicsLog"))
        previous = request_id_var.get()
        token = request_id_var.set("physics-request-a")
        ctx = ResolveContext()
        try:
            with generation_world_log("world-a", mode="light", root=self.root / "generation") as a:
                first = runtime({"gravity_acceleration_m_s2": None}, ctx=ctx)
                self.assertEqual(first, runtime({"gravity_acceleration_m_s2": None}, ctx=ctx))
                with generation_world_log("world-b", mode="light", root=self.root / "generation") as b:
                    runtime({-1: 1}, ctx=ResolveContext())
        finally:
            request_id_var.reset(token)
        self.assertEqual(request_id_var.get(), previous)
        runtime({"g": 1}, ctx=ResolveContext())
        sink = self.physics(self.root / "physics/physicsLog.log")
        self.assertEqual(len(sink), 3)
        self.assertEqual(len(self.physics(a)), 1)
        self.assertEqual(len(self.physics(b)), 1)
        self.assertEqual(sink[0], self.physics(a)[0])
        self.assertEqual(sink[0]["selected_default"], first.diagnostics[0].selected)
        self.assertEqual(sink[0]["arguments"], first.diagnostics[0].cause.arguments.model_dump(mode="json"))
        self.assertEqual(sink[0]["path"], first.diagnostics[0].cause.path.model_dump(mode="json"))
        self.assertEqual(sink[0]["issue_type"], "PhysicsGravityTypeError")
        self.assertEqual(sink[0]["code"], first.diagnostics[0].cause.code.value)
        self.assertEqual(sink[0]["location"], ["gravity_acceleration_m_s2"])
        self.assertNotIn("selected_default", sink[1])
        self.assertNotIn("arguments", sink[1])
        self.assertNotIn("path", sink[1])
        self.assertEqual(sink[0]["request_id"], "physics-request-a")
        self.assertEqual(sink[-1]["request_id"], previous)
        self.assertEqual(self.rows(self.root / "jsonValidation/resolve.log"), [])

    def test_runtime_and_silent_results_match_and_processing_continues(self):
        cases = ({}, {"gravity_acceleration_m_s2": 0}, {"gravity_acceleration_m_s2": 3},
                 {"gravity_acceleration_m_s2": None}, None, {-1: 1},
                 {"gravity_acceleration_m_s2": None, "g": 1})
        for operation, validation in ((runtime, False), (validate, True)):
            for raw in cases:
                with self.subTest(operation=operation.__name__, raw=raw):
                    emitted = ResolveContext(validate_only=validation)
                    silent = ResolveContext(validate_only=validation, collect_only=True)
                    result = operation(raw, ctx=emitted)
                    before = len(self.physics(self.root / "physics/physicsLog.log"))
                    self.assertEqual(result, operation(raw, ctx=silent))
                    self.assertEqual(emitted.report, silent.report)
                    self.assertEqual(before, len(self.physics(self.root / "physics/physicsLog.log")))
                    if validation:
                        self.assertFalse(emitted.report.diagnostics)
        # The independent call after refusals still succeeds, without warning.
        final = runtime({"gravity_acceleration_m_s2": 0}, ctx=ResolveContext())
        self.assertEqual(final.settings.gravity_acceleration_m_s2, 0)
        rows = self.physics(self.root / "physics/physicsLog.log")
        self.assertEqual(len(rows), 5)  # fallback + root shape + invalid key + two mixed causes
        self.assertEqual(self.rows(self.root / "jsonValidation/resolve.log"), [])

    def test_refusals_are_request_local_and_fallback_repeats_in_new_report(self):
        ctx = ResolveContext()
        for _ in range(2):
            runtime({"g": 1}, ctx=ctx)
        self.assertEqual(len(ctx.errors), 2)
        for _ in range(2):
            runtime({"gravity_acceleration_m_s2": None}, ctx=ResolveContext())
        rows = self.physics(self.root / "physics/physicsLog.log")
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["level"] == "WARNING" for row in rows))
