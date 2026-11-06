import logging
import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from app.application.time.logging.timeOperationLog import TimeOperationLog
from app.dataModel.time.diagnostics.events import CurrentLogContext, HistoricalLogContext, TimeFaultLog, TimeLogOperation
from app.dataModel.time.results.errors import TimeStateUnavailable, TimeUnavailableReason
from tests.time.test_time_core import publication
from tests.time.test_time_core import point, custom_settings
from app.core.logging.formatting import JsonLogFormatter
from app.core.logging.context import request_id_var
from app.dataModel.time.changes.advance import PrepareAdvance, TimeAdvanceProposal
from app.dataModel.time.values.duration import TimeDuration
from app.dataModel.time.values.interval import TimeInterval
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.time.results.errors import TimeAdvanceMustBePositive, TimeRangeOverflow, TimeArithmeticKind, TimePublicationConflict, TimeInactiveTimeline
from app.dataModel.world.calendar.projection.request import CalendarBudget, CalendarProjectionInput, CalendarResolveInput, ResolvedCalendarAt, CalendarVersionRef
from app.dataModel.world.calendar.projection.errors import CalendarSourceMismatch, CalendarScopeMismatch, CalendarBudgetExceeded, CalendarInvalid, CalendarTimeOverflow, CalendarFieldIssue, CalendarIssueCode
from app.dataModel.world.calendar.enums.rules import CalendarConversionKind
from app.dataModel.world.calendar.dates.date import CalendarDate
from app.dataModel.world.calendar.dates.clock import CalendarClockTime
from app.dataModel.registryKey import RegistryKey


class TimeOperationLogTests(unittest.TestCase):
    def test_semantic_methods_and_formatter(self):
        producer = TimeOperationLog()
        source = publication()
        capture = TimeCapture(publication=source, point=point())
        request = PrepareAdvance(operation_id="op", base=capture, duration=TimeDuration(seconds=0, nanoseconds=0))
        settings = custom_settings()
        resolved = ResolvedCalendarAt(source=source, version=CalendarVersionRef(calendar_key=settings.selected, publication=source), settings=settings)
        budget = CalendarBudget(max_rule_checks=100, max_year_patterns=100)
        project = CalendarProjectionInput(point=point(), capture=capture, calendar=settings.selected, resolved=resolved, budget=budget)
        reverse = CalendarResolveInput(resolved=resolved, calendar=settings.selected, scope=point().scope,
            date=CalendarDate(year=0, span=RegistryKey("month"), day=1),
            time=CalendarClockTime(hour=0, minute=0, second=0, nanoseconds=0), budget=budget)
        calendar_failures = (
            (CalendarSourceMismatch(expected=source, actual=source), "calendar_source_mismatch"),
            (CalendarBudgetExceeded(budget=budget), "calendar_budget"),
            (CalendarInvalid(issues=(CalendarFieldIssue.at(CalendarBudget, ("max_rule_checks",), CalendarIssueCode.INVALID_CALENDAR, "invalid"),)), "calendar_invalid"),
            (CalendarTimeOverflow(operation=CalendarConversionKind.PROJECT), "calendar_overflow"),
        )
        token = request_id_var.set("request-test")
        try:
            with patch.object(producer._logger, "log") as log:
                producer.emit_advance_prepared(TimeAdvanceProposal(operation_id="op", base=capture,
                    interval=TimeInterval(start=point(), end=point(1))))
                self.assertEqual(log.call_args.kwargs["extra"]["end_seconds"], 1)
                for failure, code in ((TimeAdvanceMustBePositive(duration=request.duration), "advance_nonpositive"),
                                      (TimeRangeOverflow(operation=TimeArithmeticKind.ADD), "range_overflow")):
                    producer.emit_advance_refused(request, failure)
                    self.assertEqual(log.call_args.kwargs["extra"]["code"], code)
                for failure, code in ((TimePublicationConflict(expected=source, observed=source), "publication_conflict"),
                                      (TimeInactiveTimeline(requested="main", active=None), "inactive_timeline")):
                    producer.emit_current_refused(source, failure)
                    self.assertEqual(log.call_args.kwargs["extra"]["code"], code)
                for failure, code in calendar_failures:
                    producer.emit_project_refused(project, failure)
                    self.assertEqual(log.call_args.kwargs["extra"]["code"], code)
                    producer.emit_resolve_refused(reverse, failure)
                    self.assertEqual(log.call_args.kwargs["extra"]["code"], code)
                producer.emit_project_refused(project, CalendarScopeMismatch(expected=point().scope, actual=point().scope))
                self.assertEqual(log.call_args.kwargs["extra"]["code"], "calendar_scope_mismatch")
                for call in log.call_args_list:
                    record = logging.LogRecord("app.time.operations", call.args[0], __file__, 1, call.args[1], (), None)
                    record.__dict__.update(call.kwargs["extra"])
                    data = json.loads(JsonLogFormatter().format(record))
                    self.assertEqual(data["request_id"], "request-test")
                    self.assertFalse({"exc", "payload", "issues", "settings", "capture"} & data.keys())
        finally:
            request_id_var.reset(token)

    def test_current_and_historical_correlation(self):
        producer = TimeOperationLog()
        source = publication()
        failure = TimeStateUnavailable(world_uid=source.world_uid, reason=TimeUnavailableReason.SOURCE_UNRESOLVED)
        for expected in (source, source.model_copy(update={"snapshot_head": None})):
            with patch.object(producer._logger, "log") as log:
                producer.emit_current_refused(expected, failure)
                log.assert_called_once()
                self.assertEqual(log.call_args.args[0], logging.WARNING)
                extra = log.call_args.kwargs["extra"]
                self.assertEqual(extra["timeline_id"], "main")
                self.assertEqual(extra["publication_id"], "publication")
                self.assertNotIn("reason", extra)
        assert source.snapshot_head is not None
        with patch.object(producer._logger, "log") as log:
            producer.emit_historical_refused(source.snapshot_head, failure)
            self.assertIsNone(log.call_args.kwargs["extra"]["publication_id"])

    def test_cancellation_fault_and_sink_failure(self):
        producer = TimeOperationLog()
        context = CurrentLogContext(expected=publication())
        with patch.object(producer._logger, "log", side_effect=OSError("sink")) as log:
            producer.emit_cancelled(context)
            producer.emit_fault(context)
            self.assertEqual(log.call_count, 2)
            self.assertEqual([call.args[0] for call in log.call_args_list], [logging.DEBUG, logging.ERROR])
        source = publication().snapshot_head
        assert source is not None
        with patch.object(producer._logger, "log") as log:
            producer.emit_fault(HistoricalLogContext(snapshot=source))
            self.assertIsNone(log.call_args.kwargs["extra"]["publication_id"])

    def test_admission_precedes_delivery(self):
        producer = TimeOperationLog()
        good = TimeFaultLog(operation=TimeLogOperation.READ_CURRENT, world_uid="world",
                            timeline_id=None, operation_id=None, publication_id=None, snapshot=None)
        class ExtraFault(TimeFaultLog):
            payload: str
        bad = good.model_copy(update={"operation_id": "invalid"})
        with self.assertRaises(ValidationError):
            CurrentLogContext.model_validate({"operation": "read_current", "expected": publication()})
        source = publication().snapshot_head
        assert source is not None
        nested = good.model_copy(update={"snapshot": source.model_copy(update={"snapshot_id": 3})})
        with patch.object(producer._logger, "log") as log:
            with self.assertRaises(ValidationError):
                producer.emit(nested)
            with self.assertRaises(ValidationError):
                producer.emit(bad)
            with self.assertRaises(TypeError):
                producer.emit(ExtraFault(**good.model_dump(), payload="secret"))
            log.assert_not_called()
