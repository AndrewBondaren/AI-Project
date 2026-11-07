"""Contracts at the stdlib logger-name and file delivery boundaries."""
import ast
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.core.logging.consumers import get_consumer_logger
from app.core.logging.contracts import LogConsumer, LogRoute, LogSink, UnknownLogConsumerError
from app.core.logging.fileRouter import DomainFileRouter
from app.core.logging.routes import _index_routes, route_for, ROUTES


class ConsumerTests(unittest.TestCase):
    def test_strict_consumer_and_complete_catalog(self):
        with self.assertRaises(TypeError):
            get_consumer_logger("app.time.operations")
        with self.assertRaises(ValidationError):
            LogRoute.model_validate(dict(consumer="http", sink=LogSink.HTTP,
                                         server_enabled=True, generation_enabled=False))
        for invalid in (ROUTES[:-1], ROUTES + ROUTES[:1]):
            with self.assertRaises(ValueError):
                _index_routes(invalid)
        for consumer in LogConsumer:
            logger = get_consumer_logger(consumer)
            self.assertIs(route_for(logger.name).consumer, consumer)

    def test_unknown_is_a_contract_error_before_any_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for profile in ("server", "script"):
                router = DomainFileRouter(profile=profile, logs_dir=base, script_service="test")
                try:
                    with patch.object(router, "handleError") as delivery_error:
                        with self.assertRaises(UnknownLogConsumerError) as caught:
                            router.handle(logging.makeLogRecord({"name": "unregistered.consumer"}))
                        self.assertEqual(caught.exception.logger_name, "unregistered.consumer")
                        delivery_error.assert_not_called()
                finally:
                    router.close()
            self.assertEqual(list(base.iterdir()), [])

    def test_pack_config_keeps_effective_debug_level(self):
        import tomllib
        with (Path(__file__).resolve().parents[1] / "config.toml").open("rb") as stream:
            overrides = tomllib.load(stream)["logger_levels"]
        for consumer in (LogConsumer.PACK_BAKE, LogConsumer.PACK_REFINE_GRADE):
            self.assertEqual(overrides[consumer.value], overrides["app.application.worldData.pack"])

    def test_debug_capture_still_receives_relocated_generator_events(self):
        from app.application.worldData.debugStructureRotations import capture_generator_logs
        from app.application.worldData.generators.climate.loggingHelpers import logger

        handler = logging.NullHandler()
        with patch.object(handler, "handle") as capture:
            with capture_generator_logs(handler):
                logger.warning("inside capture")
            logger.warning("after capture")
            capture.assert_called_once()
            self.assertEqual(capture.call_args.args[0].name, LogConsumer.CLIMATE.value)

    def test_time_adapter_relocation_and_contract_error_propagation(self):
        from app.application.time.logging import timeOperationLog
        from app.dataModel.time.diagnostics.events import CurrentLogContext
        from tests.time.test_time_core import publication

        context = CurrentLogContext(expected=publication())
        with patch.object(timeOperationLog, "__name__", "relocated.time.diagnostics"):
            adapter = timeOperationLog.TimeOperationLog()
        self.assertIs(route_for(adapter._logger.name).sink, LogSink.TIME_OPERATIONS)
        with patch.object(adapter._logger, "log", side_effect=UnknownLogConsumerError("typo")):
            with self.assertRaises(UnknownLogConsumerError):
                adapter.emit_fault(context)

    def test_module_named_producers_have_explicit_runtime_routes(self):
        # A move of an unmigrated runtime emitter must be caught before deployment.
        backend = Path(__file__).resolve().parents[1]
        for path in (backend / "app").rglob("*.py"):
            source = path.read_text(encoding="utf-8-sig")
            if "getLogger(__name__)" not in source:
                continue
            if any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                   and call.func.attr == "getLogger" and call.args
                   and isinstance(call.args[0], ast.Name) and call.args[0].id == "__name__"
                   for call in ast.walk(ast.parse(source))):
                with self.subTest(path=path):
                    name = ".".join(path.relative_to(backend).with_suffix("").parts)
                    self.assertIs(route_for(name).sink, LogSink.CORE_RUNTIME)
