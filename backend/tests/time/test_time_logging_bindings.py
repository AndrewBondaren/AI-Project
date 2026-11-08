from asyncio import CancelledError
from copy import deepcopy
import unittest
from unittest.mock import patch

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.jsonValidation.types import wire_loc
from app.application.worldData.timeSettings.admission.settings import resolve_world_time_settings
from app.application.time.logging.timeOperationLog import TimeOperationLog
from app.application.time.composition.factory import make_calendar_projector, make_calendar_validator
from app.application.worldData.timeSettings.factory import make_calendar_settings_pipeline, make_hours_settings_pipeline
from app.core.logging.contracts import LogConsumer
from app.dataModel.registryKey import RegistryKey
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.world.calendar.enums.rules import CalendarConversionKind
from app.dataModel.world.calendar.projection.errors import (
    CalendarBudgetExceeded, CalendarFieldIssue, CalendarInvalid, CalendarIssueCode,
    CalendarScopeMismatch, CalendarSourceMismatch, CalendarTimeOverflow,
)
from app.dataModel.world.calendar.projection.request import CalendarBudget, CalendarVersionRef
from app.dataModel.world.settings.timeOperations.changes import (
    CalendarAnchorReplacement, CalendarUpdate, HoursChange, SettingsPreparationBase,
)
from app.dataModel.world.settings.timeOperations.read import ResolveCalendarAt, TimeSettingsCapture
from app.dataModel.world.settings.timeOperations.results import (
    PreparedTimeSettingsChange, SettingsAnchorRequired, SettingsInvalid,
)
from tests.time.test_time_core import custom_settings, point, publication


class ProjectBindingTests(unittest.TestCase):
    def setUp(self):
        settings = custom_settings()
        self.first = settings.calendars.entries[0]
        self.second = self.first.model_copy(update={"definition": self.first.definition.model_copy(
            update={"system_calendar": RegistryKey("second")})})
        registry = settings.calendars.model_copy(update={"entries": (self.first, self.second)})
        settings = settings.model_copy(update={"calendars": registry})
        source = publication()
        self.base = SettingsPreparationBase(
            operation_id="change", budget=CalendarBudget(max_rule_checks=100, max_year_patterns=100),
            clock=TimeCapture(publication=source, point=point(9 * 3600)),
            capture=TimeSettingsCapture(source=source, settings=settings, versions=tuple(
                CalendarVersionRef(calendar_key=e.definition.system_calendar, publication=source)
                for e in registry.entries)),
        )
        self.projector = make_calendar_projector()
        self.validator = make_calendar_validator()
        self.calendar = make_calendar_settings_pipeline(self.validator, self.projector)
        self.hours = make_hours_settings_pipeline(self.validator, self.projector)

    def change_hours(self, hours: int = 12, anchors: tuple[CalendarAnchorReplacement, ...] = ()):
        return self.hours.prepare_hours_change(HoursChange(base=self.base, hours_per_day=hours, anchors=anchors))

    def update_calendar(self):
        return self.calendar.prepare_calendar_update(CalendarUpdate(base=self.base, entry=self.first))

    def test_hours_continuation_and_explicit_anchor(self):
        before = self.base.capture.settings.model_copy(deep=True)
        replacement = CalendarAnchorReplacement(calendar=self.first.definition.system_calendar,
                                                origin=self.first.anchor.origin)
        for anchors in ((), (replacement,)):
            with self.subTest(anchors=anchors), patch.object(
                self.projector, "project", wraps=self.projector.project
            ) as project, self.assertNoLogs(LogConsumer.TIME_OPERATIONS.value, "DEBUG"):
                result = self.change_hours(anchors=anchors)
                assert isinstance(result, PreparedTimeSettingsChange)
                self.assertEqual(result.before, before)
                self.assertEqual(result.effective_at, self.base.clock.point)
                entries = result.after.calendars.entries
                self.assertEqual([e.anchor.origin.time.hour for e in entries], [0 if anchors else 9, 9])
                expected = entries[1:] if anchors else entries
                self.assertEqual([c.args[0].calendar for c in project.call_args_list],
                                 [e.definition.system_calendar for e in expected])
        self.assertEqual(self.base.capture.settings, before)

    def test_world_refusal_after_success_stops_at_first_calendar(self):
        with patch.object(self.projector, "project", wraps=self.projector.project) as project, self.assertNoLogs(
            LogConsumer.TIME_OPERATIONS.value, "DEBUG"
        ):
            result = self.change_hours(8)
            assert isinstance(result, SettingsAnchorRequired)
            self.assertEqual(result.current.hour, 9)
            self.assertEqual(result.calendar, self.first.definition.system_calendar)
            project.assert_called_once()

    def test_update_anchor_and_unknown_version(self):
        explicit = self.first.anchor.model_copy(update={"coordinate_seconds": self.base.clock.point.seconds})
        for anchor in (explicit, self.first.anchor):
            with self.subTest(anchor=anchor), self.assertNoLogs(LogConsumer.TIME_OPERATIONS.value, "DEBUG"):
                entry = self.first.model_copy(update={"anchor": anchor})
                result = self.calendar.prepare_calendar_update(CalendarUpdate(base=self.base, entry=entry))
                assert isinstance(result, PreparedTimeSettingsChange)
                self.assertEqual(result.after.calendars.entries[0].anchor.origin.time.hour,
                                 0 if anchor == explicit else 9)
        unknown = self.first.model_copy(update={"definition": self.first.definition.model_copy(
            update={"system_calendar": RegistryKey("missing")})})
        with patch.object(self.projector, "project") as project, self.assertNoLogs(LogConsumer.TIME_OPERATIONS.value, "DEBUG"):
            result = self.calendar.prepare_calendar_update(CalendarUpdate(base=self.base, entry=unknown))
            assert isinstance(result, SettingsInvalid)
            self.assertEqual(result.issues, (CalendarFieldIssue.at(
                ResolveCalendarAt, ("calendar",), CalendarIssueCode.INVALID_SETTINGS_CHANGE, "unknown calendar"
            ),))
            project.assert_not_called()

    def refusals(self):
        source = self.base.capture.source
        scope = self.base.clock.point.scope
        issue = CalendarFieldIssue.at(CalendarUpdate, ("entry",), CalendarIssueCode.INVALID_CALENDAR, "invalid")
        return (
            (CalendarBudgetExceeded(budget=self.base.budget), "calendar_budget"),
            (CalendarInvalid(issues=(issue,)), "calendar_invalid"),
            (CalendarSourceMismatch(expected=source, actual=source.model_copy(update={"publication_id": "other"})),
             "calendar_source_mismatch"),
            (CalendarScopeMismatch(expected=scope, actual=scope.model_copy(update={"timeline_id": "other"})),
             "calendar_scope_mismatch"),
            (CalendarTimeOverflow(operation=CalendarConversionKind.PROJECT), "calendar_overflow"),
        )

    def assert_world_refusal(self, refusal, result):
        if isinstance(refusal, CalendarBudgetExceeded):
            self.assertIs(result, refusal)
        else:
            assert isinstance(result, SettingsInvalid)
            if isinstance(refusal, CalendarInvalid):
                self.assertEqual(result.issues, refusal.issues)
            else:
                self.assertEqual(result.issues, (CalendarFieldIssue.at(
                    SettingsPreparationBase, ("capture",), CalendarIssueCode.INVALID_SETTINGS_CHANGE,
                    "inconsistent projection source"
                ),))

    @patch.object(TimeOperationLog, "emit")
    def test_projected_caller_outcomes(self, _emit):
        # Characterize the public results independently of event delivery.
        for caller in (self.update_calendar, self.change_hours):
            # Overflow is a typed boundary case with no real projector return path.
            for refusal, code in self.refusals():
                with self.subTest(caller=caller, code=code), patch.object(
                    self.projector, "project", return_value=refusal
                ) as project:
                    self.assert_world_refusal(refusal, caller())
                    project.assert_called_once()
            for exc in (CancelledError(), RuntimeError("projection")):
                with patch.object(self.projector, "project", side_effect=exc) as project, self.assertRaises(type(exc)) as raised:
                    caller()
                project.assert_called_once()
                self.assertIs(raised.exception, exc)

    def test_project_return_and_exception_boundary(self):
        for caller in (self.update_calendar, self.change_hours):
            for refusal, code in self.refusals():
                with self.subTest(caller=caller, code=code), patch.object(self.projector, "project", return_value=refusal) as project:
                    with self.assertNoLogs(LogConsumer.RESOLVE.value, "WARNING"), self.assertLogs(
                        LogConsumer.TIME_OPERATIONS.value, "DEBUG"
                    ) as logs:
                        self.assert_world_refusal(refusal, caller())
                    record, = logs.records
                    self.assertEqual((record.levelname, record.getMessage(), getattr(record, "operation"),
                                      getattr(record, "code")), ("WARNING", "operation_refused", "project", code))
                    self.assertEqual(getattr(record, "publication_id"), self.base.clock.publication.publication_id)
                    project.assert_called_once()
            for exc in (CancelledError(), RuntimeError("projection")):
                with patch.object(self.projector, "project", side_effect=exc), self.assertLogs(
                    LogConsumer.TIME_OPERATIONS.value, "DEBUG"
                ) as logs, self.assertRaises(type(exc)) as raised:
                    caller()
                self.assertIs(raised.exception, exc)
                record, = logs.records
                expected = ("DEBUG", "operation_cancelled") if isinstance(exc, CancelledError) else ("ERROR", "operation_failed")
                self.assertEqual((record.levelname, record.getMessage()), expected)
                self.assertEqual(getattr(record, "operation"), "project")
                self.assertEqual(getattr(record, "publication_id"), self.base.clock.publication.publication_id)

    def test_producer_failure_preserves_original_outcome_without_retry(self):
        for caller in (self.change_hours, self.update_calendar):
            for failure in (TypeError("admission"), CancelledError("emitter")):
                for refusal, code in self.refusals():
                    with self.subTest(code=code), patch.object(self.projector, "project", return_value=refusal), patch.object(
                        TimeOperationLog, "emit", side_effect=failure
                    ) as emit:
                        self.assert_world_refusal(refusal, caller())
                        emit.assert_called_once()
                        self.assertEqual(emit.call_args.args[0].code, code)
                        self.assertEqual(emit.call_args.args[0].publication_id, self.base.clock.publication.publication_id)
                for exc, activity in ((RuntimeError("project"), "operation_failed"), (CancelledError(), "operation_cancelled")):
                    with patch.object(self.projector, "project", side_effect=exc), patch.object(
                        TimeOperationLog, "emit", side_effect=failure
                    ) as emit, self.assertRaises(type(exc)) as raised:
                        caller()
                    emit.assert_called_once()
                    self.assertEqual(emit.call_args.args[0].activity, activity)
                    self.assertEqual(emit.call_args.args[0].publication_id, self.base.clock.publication.publication_id)
                    self.assertIs(raised.exception, exc)

    def test_real_project_budget_exhaustion(self):
        budget = CalendarBudget(max_rule_checks=1, max_year_patterns=1)
        self.base = self.base.model_copy(update={"budget": budget})
        with self.assertLogs(LogConsumer.TIME_OPERATIONS.value, "DEBUG") as logs:
            self.assertEqual(self.change_hours(), CalendarBudgetExceeded(budget=budget))
        record, = logs.records
        self.assertEqual(getattr(record, "code"), "calendar_budget")

    def test_real_project_rejects_missing_selected_in_both_preparations(self):
        capture = self.base.capture
        settings = capture.settings.model_copy(update={"selected": RegistryKey("missing")})
        self.base = self.base.model_copy(update={"capture": capture.model_copy(update={"settings": settings})})
        for caller in (self.update_calendar, self.change_hours):
            with self.subTest(caller=caller.__name__), self.assertNoLogs(
                LogConsumer.RESOLVE.value, "WARNING"
            ), self.assertLogs(LogConsumer.TIME_OPERATIONS.value, "DEBUG") as logs:
                result = caller()
                assert isinstance(result, SettingsInvalid)
                issue, = result.issues
                self.assertEqual(issue.path.projection(), ("selected",))
                record, = logs.records
                self.assertEqual((record.levelname, record.getMessage(), getattr(record, "operation"),
                                  getattr(record, "code")), ("WARNING", "operation_refused", "project", "calendar_invalid"))

    def test_validator_exception_after_projection_is_outside_binding(self):
        error = RuntimeError("validator")
        with patch.object(self.validator, "validate", side_effect=error), self.assertNoLogs(
            LogConsumer.TIME_OPERATIONS.value, "DEBUG"
        ), self.assertRaises(RuntimeError) as raised:
            self.update_calendar()
        self.assertIs(raised.exception, error)

    def test_world_admission_collect_only_preserves_report_and_outcome(self):
        runtime_warnings = {"default": 0, "fallback": 1, "independent": 2, "required": 1,
                            "invalid_minute": 1, "invalid_minute_and_periods": 3}
        for mode, count in runtime_warnings.items():
            raw = custom_settings().model_dump(mode="json")
            if mode == "default":
                del raw["hours_per_day"]
            if mode in ("fallback", "independent"):
                raw["hours_per_day"] = 0
            if mode == "independent":
                raw["selected"] = "missing"
            if mode == "required":
                del raw["selected"]
            if mode in ("invalid_minute", "invalid_minute_and_periods"):
                periods = raw["calendars"]["entries"][0]["definition"]["periods"]["entries"]
                if mode == "invalid_minute":
                    periods[0]["from_minute"] = 75
                else:
                    periods.append(dict(system_period="evening", display_period="Evening", from_hour=0, from_minute=75))
                    raw["selected"] = "missing"
            original = deepcopy(raw)
            for preview in (False, True):
                observations = []
                for collect in (False, True):
                    ctx = ResolveContext(validate_only=preview, collect_only=collect)
                    expected = 0 if collect or preview else count
                    resolver = LogConsumer.RESOLVE.value
                    with self.subTest(mode=mode, preview=preview, collect=collect), self.assertNoLogs(
                        LogConsumer.TIME_OPERATIONS.value, "DEBUG"
                    ), (self.assertLogs(resolver, "WARNING") if expected else self.assertNoLogs(resolver, "WARNING")) as logs:
                        try:
                            outcome = resolve_world_time_settings(raw, ctx, self.base.budget)
                        except UnresolvedModelError as exc:
                            outcome = tuple(exc.issues)
                        self.assertEqual(raw, original)
                        if logs is not None:
                            self.assertEqual(len(logs.records), expected)
                            for record in logs.records:
                                self.assertIn("WarningError", record.getMessage())
                        if mode == "invalid_minute" and not preview:
                            self.assertEqual(outcome, custom_settings())
                        if mode == "invalid_minute_and_periods" and not preview:
                            self.assertEqual(outcome, tuple(ctx.errors))
                            self.assertEqual({wire_loc(i) for i in ctx.errors}, {
                                ("selected",), ("calendars", "entries", 0, "definition", "periods")})
                        if mode.startswith("invalid_minute"):
                            issues = ctx.errors if preview else ctx.report.diagnostics
                            self.assertEqual(sum(wire_loc(i)[-1:] == ("from_minute",) for i in issues), 1)
                            if preview:
                                self.assertEqual(outcome, tuple(ctx.errors))
                        observations.append((outcome, ctx.errors, ctx.report.diagnostics))
                self.assertEqual(observations[0], observations[1])

    def test_intercalary_projection_without_weekday_or_epoch_keeps_anchor_fallback(self):
        # At four ten-hour days the custom calendar reaches the intercalary festival.
        clock = self.base.clock.model_copy(update={"point": point(144000)})
        base = self.base.model_copy(update={"clock": clock})
        original_project = self.projector.project

        def project(request):
            from app.dataModel.world.calendar.projection.result import CalendarProjection

            result = original_project(request)
            assert isinstance(result, CalendarProjection)
            self.assertEqual(result.date.span, "festival")
            self.assertEqual((result.weekday, result.epoch, result.epoch_year), (None, None, None))
            return result

        without_festival = self.first.definition.model_copy(update={"rules": ()})
        entry = self.first.model_copy(update={"definition": without_festival})
        with patch.object(self.projector, "project", side_effect=project) as observed, self.assertNoLogs(
            LogConsumer.TIME_OPERATIONS.value, "DEBUG"
        ):
            result = self.calendar.prepare_calendar_update(CalendarUpdate(base=base, entry=entry))
        observed.assert_called_once()
        assert isinstance(result, SettingsAnchorRequired)
        self.assertEqual(result.calendar, self.first.definition.system_calendar)
        self.assertEqual(result.current, self.first.anchor.origin.time)
