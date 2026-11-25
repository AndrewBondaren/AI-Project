import unittest
from asyncio import CancelledError
from unittest.mock import patch

from pydantic import ValidationError

from app.application.time.calendar.rules import Work
from app.application.time.calendar.validation import validated_indexes
from app.application.worldData.timeSettings.preparation.batchPipelineOpenPipeline import TimeSettingsBatchPipelineOpenPipeline
from app.application.worldData.timeSettings.preparation.sectionPipelineOpenPipeline import TimeSettingsSectionPipelineOpenPipeline
from app.application.worldData.timeSettings.preparation.calendarPipelineOpenPipeline import WorldCalendarSettingsPipelineOpenPipeline
from app.application.worldData.timeSettings.preparation.shared.context import CandidatePreparation
from app.dataModel.registryKey import RegistryKey
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.world.calendar.projection.request import CalendarBudget, CalendarVersionRef
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.batch import PrepareTimeSettingsBatch, SettingsBatchInputMismatch, SettingsBatchRefused
from app.dataModel.world.settings.timeOperations.changes import CalendarCreate, CalendarSelect, CalendarUpdate, CalendarRemove, SettingsPreparationBase
from app.dataModel.world.settings.timeOperations.read import TimeSettingsCapture
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from app.dataModel.world.settings.timePublication.section import PrepareTimeSettingsSection, WorldTimeSettingsSection
from app.dataModel.world.settings.timePublication.errors import SettingsSectionContextMismatch, SettingsSectionIssueCode
from tests.time.test_time_core import custom_settings, point, publication


class SettingsPreparationTests(unittest.TestCase):
    def setUp(self):
        settings = custom_settings()
        source = publication()
        self.base = SettingsPreparationBase(operation_id="op", clock=TimeCapture(publication=source, point=point(3600, 123)),
            capture=TimeSettingsCapture(source=source, settings=settings,
                versions=(CalendarVersionRef(calendar_key=settings.selected, publication=source),)),
            budget=CalendarBudget(max_rule_checks=10000, max_year_patterns=10000))
        self.batch = TimeSettingsBatchPipelineOpenPipeline()
        self.section = TimeSettingsSectionPipelineOpenPipeline()

    def select(self, base=None):
        return CalendarSelect(base=base or self.base, calendar=self.base.capture.settings.selected)

    def test_all_single_operations_revalidate_before_algorithm(self):
        from app.application.time.calendar.validation import CalendarValidator
        from app.application.time.calendar.projection import CalendarProjector
        from app.application.worldData.timeSettings.preparation.epochPipelineOpenPipeline import WorldEpochSettingsPipelineOpenPipeline
        from app.application.worldData.timeSettings.preparation.hoursPipelineOpenPipeline import WorldHoursSettingsPipelineOpenPipeline
        from app.dataModel.world.settings.timeOperations.changes import HoursChange, EpochCreate, EpochUpdate, EpochRemove
        from app.dataModel.world.calendar.epochs.epoch import WorldCalendarEpoch
        calendar = WorldCalendarSettingsPipelineOpenPipeline(CalendarValidator(), CalendarProjector())
        hours = WorldHoursSettingsPipelineOpenPipeline(CalendarValidator(), CalendarProjector())
        epochs = WorldEpochSettingsPipelineOpenPipeline(CalendarValidator())
        entry = self.base.capture.settings.calendars.entries[0]
        key = self.base.capture.settings.selected
        epoch = WorldCalendarEpoch(system_epoch=RegistryKey("reign"), display_epoch="Reign", description="",
            calendar=key, start_seconds=0, start_nanoseconds=0, start_year_label=1)
        cases = (
            (calendar.prepare_calendar_create, CalendarCreate(base=self.base, entry=entry)),
            (calendar.prepare_calendar_update, CalendarUpdate(base=self.base, entry=entry)),
            (calendar.prepare_calendar_select, self.select()),
            (calendar.prepare_calendar_remove, CalendarRemove(base=self.base, calendar=key, replacement=key)),
            (hours.prepare_hours_change, HoursChange(base=self.base, hours_per_day=24, anchors=())),
            (epochs.prepare_epoch_create, EpochCreate(base=self.base, epoch=epoch)),
            (epochs.prepare_epoch_update, EpochUpdate(base=self.base, epoch=epoch)),
            (epochs.prepare_epoch_remove, EpochRemove(base=self.base, epoch=epoch.system_epoch)),
        )
        bad_base = self.base.model_copy(update={"budget": self.base.budget.model_copy(update={
            "max_rule_checks": 0, "max_year_patterns": 0})})
        for operation, request in cases:
            with self.subTest(operation=operation.__name__), patch(
                operation.__module__ + "." + operation.__name__.removeprefix("prepare_"),
                side_effect=AssertionError("algorithm must not run")):
                with self.assertRaises(ValidationError) as caught:
                    operation(request.model_copy(update={"base": bad_base}))
                self.assertEqual(tuple(error["loc"] for error in caught.exception.errors()), (
                    ("base", "budget", "max_rule_checks"), ("base", "budget", "max_year_patterns")))

    def test_dependent_commands_use_candidate_without_public_dispatch(self):
        entry = self.base.capture.settings.calendars.entries[0]
        key = RegistryKey("added")
        entry = entry.model_copy(update={"definition": entry.definition.model_copy(update={"system_calendar": key})})
        request = PrepareTimeSettingsBatch(commands=(CalendarCreate(base=self.base, entry=entry),
            CalendarSelect(base=self.base, calendar=key), CalendarUpdate(base=self.base, entry=entry)))
        before = self.base.model_copy(deep=True)
        with patch.object(WorldCalendarSettingsPipelineOpenPipeline, "prepare_calendar_create", side_effect=AssertionError("public dispatch")), \
             patch.object(WorldCalendarSettingsPipelineOpenPipeline, "prepare_calendar_update", side_effect=AssertionError("public dispatch")):
            result = self.batch.prepare_batch(request)
        self.assertIsInstance(result, PreparedTimeSettingsChange)
        self.assertEqual(result.before, before.capture.settings)
        self.assertEqual(result.after.selected, key)
        self.assertEqual(result.after.calendars.entry_for(key).anchor.coordinate_nanoseconds, 123)
        self.assertEqual(self.base, before)
        reverse = self.batch.prepare_batch(PrepareTimeSettingsBatch(commands=(request.commands[1], request.commands[0])))
        self.assertIsInstance(reverse, SettingsBatchRefused)
        self.assertEqual(reverse.command_index, 0)

    def test_all_mismatched_indices_before_any_execution(self):
        other = self.base.model_copy(update={"operation_id": "other"})
        budget = self.base.model_copy(update={"budget": CalendarBudget(max_rule_checks=99, max_year_patterns=99)})
        request = PrepareTimeSettingsBatch(commands=(self.select(), self.select(other), self.select(), self.select(budget)))
        with patch.object(CandidatePreparation, "prepare", side_effect=AssertionError("must not execute")):
            result = self.batch.prepare_batch(request)
        self.assertIsInstance(result, SettingsBatchInputMismatch)
        self.assertEqual(result.indices, (1, 3))
        with self.assertRaises(ValidationError):
            SettingsBatchInputMismatch(request=request, indices=(1,))

    def test_budget_is_cumulative_and_failure_keeps_original_index(self):
        work = Work.from_budget(self.base.budget)
        validated_indexes(self.base.capture.settings, self.base.budget, work=work)
        spent = self.base.budget.max_year_patterns - work.patterns
        self.assertGreater(spent, 0)
        base = self.base.model_copy(update={"budget": CalendarBudget(max_rule_checks=10000, max_year_patterns=spent)})
        command = self.select(base)
        self.assertIsInstance(self.batch.prepare_batch(PrepareTimeSettingsBatch(commands=(command,))), PreparedTimeSettingsChange)
        result = self.batch.prepare_batch(PrepareTimeSettingsBatch(commands=(command, command)))
        self.assertIsInstance(result, SettingsBatchRefused)
        self.assertEqual(result.command_index, 1)
        self.assertIsInstance(result.reason, CalendarBudgetExceeded)

    def test_fault_and_cancellation_propagate(self):
        for error in (RuntimeError("fault"), CancelledError()):
            with self.subTest(error=type(error)), patch.object(CandidatePreparation, "prepare", side_effect=error):
                with self.assertRaises(type(error)):
                    self.batch.prepare_batch(PrepareTimeSettingsBatch(commands=(self.select(),)))

    def test_admission_revalidates_and_rejects_empty(self):
        with self.assertRaises(ValidationError):
            PrepareTimeSettingsBatch(commands=())
        request = PrepareTimeSettingsBatch(commands=(self.select(),)).model_copy(update={"commands": ()})
        with self.assertRaises(ValidationError):
            self.batch.prepare_batch(request)

    def test_epoch_dependencies_and_hours_use_working_settings(self):
        from app.dataModel.world.calendar.epochs.epoch import WorldCalendarEpoch
        from app.dataModel.world.settings.timeOperations.changes import EpochCreate, EpochRemove, HoursChange
        entry = self.base.capture.settings.calendars.entries[0]
        key = RegistryKey("added")
        entry = entry.model_copy(update={"definition": entry.definition.model_copy(update={"system_calendar": key})})
        epoch = WorldCalendarEpoch(system_epoch=RegistryKey("reign"), display_epoch="Reign", description="",
            calendar=key, start_seconds=0, start_nanoseconds=0, start_year_label=1)
        create = CalendarCreate(base=self.base, entry=entry)
        add_epoch = EpochCreate(base=self.base, epoch=epoch)
        remove_epoch = EpochRemove(base=self.base, epoch=epoch.system_epoch)
        remove_calendar = CalendarRemove(base=self.base, calendar=key, replacement=self.base.capture.settings.selected)
        result = self.batch.prepare_batch(PrepareTimeSettingsBatch(commands=(create, add_epoch,
            HoursChange(base=self.base, hours_per_day=24, anchors=()), remove_epoch, remove_calendar)))
        self.assertIsInstance(result, PreparedTimeSettingsChange)
        self.assertEqual(result.after.hours_per_day, 24)
        self.assertIsNone(result.after.calendars.entry_for(key))
        refused = self.batch.prepare_batch(PrepareTimeSettingsBatch(commands=(create, add_epoch, remove_calendar, remove_epoch)))
        self.assertIsInstance(refused, SettingsBatchRefused)
        self.assertEqual(refused.command_index, 2)
        from app.dataModel.world.settings.timeOperations.results import SettingsInUse
        self.assertIsInstance(refused.reason, SettingsInUse)

    def test_section_aggregates_context_and_does_not_reprepare(self):
        result = self.batch.prepare_batch(PrepareTimeSettingsBatch(commands=(self.select(),)))
        expected = publication().model_copy(update={"world_uid": "other", "snapshot_head": None})
        request = PrepareTimeSettingsSection(change=result, operation_id="other", expected_world=expected)
        refusal = self.section.prepare_section(request)
        self.assertIsInstance(refusal, SettingsSectionContextMismatch)
        self.assertEqual(tuple(issue.code for issue in refusal.issues), tuple(SettingsSectionIssueCode))
        for issues in (tuple(reversed(refusal.issues)), (refusal.issues[0], refusal.issues[0]),
                       (*refusal.issues, refusal.issues[0])):
            with self.subTest(issues=tuple(issue.code for issue in issues)), self.assertRaises(ValidationError):
                SettingsSectionContextMismatch(issues=issues)
            unchecked = refusal.model_copy(update={"issues": issues})
            for validate in (lambda: SettingsSectionContextMismatch.model_validate(unchecked),
                             lambda: SettingsSectionContextMismatch.model_validate_json(unchecked.model_dump_json())):
                with self.assertRaises(ValidationError):
                    validate()
        from app.dataModel.world.settings.timePublication.errors import SettingsSectionRelationIssue
        other_request = request.model_copy(update={"operation_id": "third"})
        foreign_issue = SettingsSectionRelationIssue(code=SettingsSectionIssueCode.OPERATION_MISMATCH, request=other_request)
        with self.assertRaises(ValidationError):
            SettingsSectionContextMismatch(issues=(foreign_issue, *refusal.issues[1:]))
        with patch.object(CandidatePreparation, "prepare", side_effect=AssertionError("must not prepare")):
            section = self.section.prepare_section(PrepareTimeSettingsSection(change=result,
                operation_id=result.operation_id, expected_world=result.expected))
        self.assertIsInstance(section, WorldTimeSettingsSection)
        self.assertEqual(section.patches[0].change, result)
        self.assertEqual(result.before, result.after)
        self.assertEqual(WorldTimeSettingsSection.model_validate_json(section.model_dump_json()), section)
        bad_patch = section.patches[0].model_copy(update={"header": section.patches[0].header.model_copy(
            update={"format_version": 2, "ref": section.patches[0].header.ref.model_copy(update={"ordinal": -1})})})
        bad = section.model_copy(update={"patches": (bad_patch,), "header": section.header.model_copy(update={"format_version": 2})})
        with self.assertRaises(ValidationError) as caught:
            WorldTimeSettingsSection.model_validate(bad)
        paths = {detail["loc"] for detail in caught.exception.errors()}
        self.assertIn(("header", "format_version"), paths)
        self.assertIn(("patches", 0, "header", "format_version"), paths)
        self.assertIn(("patches", 0, "header", "ref", "ordinal"), paths)
