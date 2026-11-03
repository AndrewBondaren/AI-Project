import json
import unittest

from pydantic import ValidationError

from app.application.time.changes.lifecycle import TimeLifecycle
from app.application.time.composition.factory import make_calendar_projector, make_calendar_validator, make_time_advance_pipeline
from app.application.time.pure.arithmetic import TimeArithmetic
from app.application.time.pure.conversions import TimeConversions
from app.application.worldData.timeSettings.factory import make_hours_settings_pipeline
from app.application.worldData.timeSettings.reader import WorldCalendarResolver
from app.dataModel.time.changes.advance import PrepareAdvance
from app.dataModel.time.operations.arithmetic import AddDurationInput, ComparePointsInput, MakeIntervalInput
from app.dataModel.time.operations.conversion import HoursInput, SecondsInput
from app.dataModel.time.operations.lifecycle import BindInitialTime, RebindBranchTime
from app.dataModel.time.reads.capture import TimeCapture
from app.dataModel.time.results.errors import TimeAdvanceMustBePositive, TimeIntervalReversed, TimeRangeOverflow, TimeScopeMismatch
from app.dataModel.time.storage.initial import InitialTimeFacts
from app.dataModel.time.storage.state import PublicationTimeState, StoredTimeState, TimeClockState
from app.dataModel.time.values.interval import TimeInterval
from app.dataModel.time.values.point import MAX_SECONDS, TimePoint
from app.dataModel.world.calendar.enums.rules import CalendarPredicateKind
from app.dataModel.world.calendar.rules.predicates import CalendarCondition, YearModuloPredicate, YearRangePredicate
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded, CalendarInvalid
from app.dataModel.world.calendar.projection.request import CalendarBudget, CalendarProjectionInput, CalendarResolveInput, CalendarVersionRef, ValidateCalendarInput
from app.dataModel.world.calendar.projection.result import CalendarProjection
from app.dataModel.world.settings.timeOperations.changes import HoursChange, SettingsPreparationBase
from app.dataModel.world.settings.timeOperations.read import ResolveCalendarAt, TimeSettingsCapture
from app.dataModel.world.settings.timeOperations.results import SettingsAnchorRequired
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef
from app.dataModel.registryKey import RegistryKey


def point(seconds=0, nanos=0, timeline="main"):
    return TimePoint(world_uid="world", timeline_id=timeline, seconds=seconds, nanoseconds=nanos)


def publication():
    return WorldPublicationRef(world_uid="world", publication_id="publication", active_timeline_id="main",
                               gameplay_started=True, snapshot_head=WorldSnapshotRef(world_uid="world", timeline_id="parent",
                               snapshot_id="head"), pack_hash="a"*64)


class TimeCoreTests(unittest.TestCase):
    def test_publication_state_tracks_active_branch_before_first_snapshot(self):
        state = TimeClockState(point=point())
        inherited = publication()
        headless = inherited.model_copy(update={"snapshot_head": None})
        for source in (headless, inherited):
            bound = PublicationTimeState(publication=source, state=state)
            self.assertEqual(bound.state.point, point())
        for source in (
            headless.model_copy(update={"world_uid": "another"}),
            headless.model_copy(update={"gameplay_started": False}),
            inherited.model_copy(update={"active_timeline_id": "other"}),
        ):
            with self.assertRaises(ValidationError):
                PublicationTimeState(publication=source, state=state)

    def test_arithmetic(self):
        one = TimeConversions.from_seconds(SecondsInput(seconds=0, nanoseconds=1)).duration
        start = point(-1, 999999999)
        end = TimeArithmetic.add(AddDurationInput(point=start, duration=one)).point
        self.assertEqual(end, point())
        self.assertEqual(TimeArithmetic.elapsed(TimeInterval(start=start, end=end)).duration, one)
        self.assertIsInstance(TimeArithmetic.add(AddDurationInput(point=point(MAX_SECONDS, 999999999), duration=one)), TimeRangeOverflow)
        self.assertIsInstance(TimeArithmetic.elapsed(TimeInterval(start=point(-MAX_SECONDS-1), end=end)), TimeRangeOverflow)
        self.assertIsInstance(TimeArithmetic.interval(MakeIntervalInput(start=end, end=start)), TimeIntervalReversed)
        self.assertIsInstance(TimeArithmetic.compare(ComparePointsInput(left=end, right=point(timeline="other"))), TimeScopeMismatch)
        self.assertIsInstance(TimeConversions.from_hours(HoursInput(hours=MAX_SECONDS)), TimeRangeOverflow)
        self.assertEqual(TimeConversions.from_hours(HoursInput(hours=1)).duration.seconds, 3600)
        for value in (False, 0.0, "0"):
            with self.assertRaises(ValidationError):
                point(value)

    def test_prepare(self):
        base = TimeCapture(publication=publication(), point=point())
        pipeline = make_time_advance_pipeline()
        for nanos in (0, 1):
            duration = TimeConversions.from_seconds(SecondsInput(seconds=0, nanoseconds=nanos)).duration
            request = PrepareAdvance(operation_id="operation", base=base, duration=duration)
            result = pipeline.prepare_advance(request)
            if nanos:
                self.assertEqual(result.interval.end, point(0, 1))
                self.assertEqual(result, pipeline.prepare_advance(request))
            else:
                self.assertIsInstance(result, TimeAdvanceMustBePositive)
        self.assertEqual(base.point, point())

    def test_lifecycle(self):
        initial = InitialTimeFacts(world_uid="world", seconds=0, nanoseconds=0)
        state = TimeLifecycle.bind_initial(BindInitialTime(world_uid="world", timeline_id="main", initial=initial))
        self.assertEqual(state.point, point())
        ref = SectionStateRef(snapshot=WorldSnapshotRef(world_uid="world", timeline_id="main", snapshot_id="s"),
                              section_key=RegistryKey("time"), format_version=1)
        rebound = TimeLifecycle.rebind_branch(RebindBranchTime(source=StoredTimeState(ref=ref, state=state),
                                                               target_timeline_id="branch"))
        self.assertEqual(rebound.point, point(timeline="branch"))


def festival_condition(first: int = 1, last: int = 1, *, modulo: YearModuloPredicate | None = None) -> CalendarCondition:
    years = YearRangePredicate(kind=CalendarPredicateKind.YEAR_RANGE, first=first, last=last)
    return CalendarCondition(all_of=(years,) if modulo is None else (years, modulo), none_of=())


def custom_settings(condition: CalendarCondition | None = None) -> WorldTimeSettings:
    if condition is None:
        condition = festival_condition()
    span = dict(span="month", days=2, counts_in_week=True, season=None)
    insert = dict(kind="insert_span", condition=condition.model_dump(mode="json"),
                  after="month", value=dict(span="festival", days=1, counts_in_week=False, season=None))
    definition = dict(system_calendar="custom", display_calendar="Custom", description="", numbering="astronomical",
                      spans=dict(entries=[dict(system_span=k, display_span=k, role=r) for k,r in
                                          (("month","month"), ("festival","intercalary"))]),
                      seasons=dict(entries=[]), periods=dict(entries=[dict(system_period="day", display_period="Day", from_hour=0)]),
                      weekdays=dict(entries=[dict(system_weekday=k, display_weekday=k) for k in ("a","b","c")]),
                      base_year=[span], rules=[insert], week_mode="continuous", week_anchor_index=0, week_anchor_ordinal=0)
    anchor = dict(coordinate_seconds=0, coordinate_nanoseconds=0, origin=dict(date=dict(year=0, span="month", day=1),
                  time=dict(hour=0, minute=0, second=0, nanoseconds=0)))
    return WorldTimeSettings.model_validate_json(json.dumps(dict(hours_per_day=10, selected="custom",
            epochs=dict(entries=[]), calendars=dict(entries=[dict(definition=definition, anchor=anchor)]))))


class CalendarTests(unittest.TestCase):
    def setUp(self):
        settings = custom_settings()
        self.clock = TimeCapture(publication=publication(), point=point())
        self.capture = TimeSettingsCapture(source=self.clock.publication, settings=settings, versions=(
            CalendarVersionRef(calendar_key=settings.selected, publication=self.clock.publication),))
        self.resolved = WorldCalendarResolver.resolve_at(ResolveCalendarAt(capture=self.capture, calendar=settings.selected))
        self.budget = CalendarBudget(max_rule_checks=100, max_year_patterns=100)

    def project(self, p):
        return make_calendar_projector().project(CalendarProjectionInput(point=p, capture=self.clock,
                   resolved=self.resolved, calendar=self.resolved.version.calendar_key, budget=self.budget))

    def test_round_trip(self):
        for seconds in (-MAX_SECONDS-1, -36000, -1, 0, 35999, 36000, 144000, 180000, MAX_SECONDS):
            p = point(seconds, 999999999)
            result = self.project(p)
            self.assertIsInstance(result, CalendarProjection)
            reverse = CalendarResolveInput(resolved=self.resolved, calendar=self.resolved.version.calendar_key,
                       scope=p.scope, budget=self.budget, date=result.date, time=result.time)
            self.assertEqual(make_calendar_projector().resolve(reverse).point, p)
        self.assertEqual(self.project(point(144000)).date.span, "festival")
        self.assertIsNone(self.project(point(144000)).weekday)
        self.assertEqual(self.project(point(180000)).weekday, "b")

    def test_budget_for_modulo_restricted_to_one_year(self):
        modulo = YearModuloPredicate(kind=CalendarPredicateKind.YEAR_MODULO, modulus=10**30, residue=1, offset=0)
        settings = custom_settings(festival_condition(modulo=modulo))
        budget = CalendarBudget(max_rule_checks=3, max_year_patterns=3)
        request = CalendarProjectionInput(
            point=point(144000), capture=self.clock, calendar=settings.selected,
            resolved=self.resolved.model_copy(update={"settings": settings}), budget=budget,
        )
        result = make_calendar_projector().project(request)
        self.assertIsInstance(result, CalendarProjection)
        self.assertEqual((result.date.year, result.date.span), (1, "festival"))
        insufficient = CalendarBudget(max_rule_checks=3, max_year_patterns=2)
        self.assertIsInstance(make_calendar_projector().project(request.model_copy(update={"budget": insufficient})),
                              CalendarBudgetExceeded)

    def test_year_regions_match_independent_day_count(self):
        from app.application.time.calendar.ordinal import CalendarIndex
        from app.application.time.calendar.rules import Work
        from app.dataModel.world.calendar.dates.date import CalendarDate
        modulo = YearModuloPredicate(kind=CalendarPredicateKind.YEAR_MODULO, modulus=3, residue=1, offset=2)
        settings = custom_settings(festival_condition(first=-17, last=12, modulo=modulo))
        entry = settings.calendars.entry_for(settings.selected)
        self.assertIsNotNone(entry)
        index = CalendarIndex(entry.definition, Work(100, 100))
        def length(year):
            return 2 + int(-17 <= year <= 12 and (year - 2) % 3 == 1)
        start = -sum(length(y) for y in range(-25, 0))
        for year in range(-25, 26):
            for day in range(length(year)):
                key = RegistryKey("festival" if day == 2 else "month")
                expected = CalendarDate(year=year, span=key, day=1 if day == 2 else day+1)
                self.assertEqual(index.locate(start+day)[0], expected)
                self.assertEqual(index.ordinal(expected), start+day)
            start += length(year)

    def test_validation_and_hours(self):
        request = ValidateCalendarInput(settings=self.capture.settings, budget=CalendarBudget(max_rule_checks=1,max_year_patterns=1))
        self.assertIsInstance(make_calendar_validator().validate(request), CalendarBudgetExceeded)
        bad = self.capture.settings.model_copy(update={"selected": RegistryKey("unknown")})
        self.assertIsInstance(make_calendar_validator().validate(ValidateCalendarInput(settings=bad,budget=self.budget)), CalendarInvalid)
        clock = TimeCapture(publication=publication(), point=point(9*3600))
        base = SettingsPreparationBase(operation_id="op", capture=self.capture, clock=clock, budget=self.budget)
        pipeline = make_hours_settings_pipeline(make_calendar_validator(), make_calendar_projector())
        self.assertIsInstance(pipeline.prepare_hours_change(HoursChange(base=base, hours_per_day=8, anchors=())), SettingsAnchorRequired)
        proposal = pipeline.prepare_hours_change(HoursChange(base=base, hours_per_day=30, anchors=()))
        self.assertEqual(proposal.after.calendars.entries[0].anchor.origin.time.hour, 9)
        self.assertEqual(proposal.before.hours_per_day, 10)

class WorldOperationTests(unittest.TestCase):
    def test_repeated_date_resolves_against_pinned_reform_version(self):
        from app.application.worldData.timeSettings.factory import make_calendar_settings_pipeline
        from app.dataModel.time.reads.capture import HistoricalTimeCapture
        from app.dataModel.world.calendar.dates.anchor import CalendarAnchor
        from app.dataModel.world.calendar.definitions.definition import CalendarEntry
        from app.dataModel.world.calendar.projection.errors import CalendarSourceMismatch
        from app.dataModel.world.settings.timeOperations.changes import CalendarUpdate
        from app.dataModel.world.settings.timeOperations.read import HistoricalTimeSettingsCapture
        from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange

        before = self.base.capture
        entry = before.settings.calendars.entry_for(self.key)
        effective = self.base.clock.point
        anchor = CalendarAnchor(coordinate_seconds=effective.seconds, coordinate_nanoseconds=effective.nanoseconds,
                                origin=entry.anchor.origin)
        pipeline = make_calendar_settings_pipeline(self.validator, self.projector)
        proposal = pipeline.prepare_calendar_update(CalendarUpdate(
            base=self.base, entry=CalendarEntry(definition=entry.definition, anchor=anchor)))
        self.assertIsInstance(proposal, PreparedTimeSettingsChange)

        snapshot = WorldSnapshotRef(world_uid=effective.world_uid, timeline_id=effective.timeline_id,
                                    snapshot_id="before_reform")
        historical = HistoricalTimeSettingsCapture(source=snapshot, settings=before.settings, versions=before.versions)
        publication_after = before.source.model_copy(update={"publication_id": "after_reform"})
        current = TimeSettingsCapture(source=publication_after, settings=proposal.after, versions=(
            CalendarVersionRef(calendar_key=self.key, publication=publication_after),))
        old_version = WorldCalendarResolver.resolve_at(ResolveCalendarAt(capture=historical, calendar=self.key))
        new_version = WorldCalendarResolver.resolve_at(ResolveCalendarAt(capture=current, calendar=self.key))
        historical_clock = HistoricalTimeCapture(snapshot=snapshot, point=point())
        current_clock = TimeCapture(publication=publication_after, point=effective)

        for version, clock in ((old_version, historical_clock), (new_version, current_clock)):
            with self.subTest(version=version.version.publication.publication_id):
                reverse = CalendarResolveInput(resolved=version, calendar=self.key, scope=effective.scope,
                                               date=anchor.origin.date, time=anchor.origin.time, budget=self.base.budget)
                self.assertEqual(self.projector.resolve(reverse).point, clock.point)
                request = CalendarProjectionInput(point=clock.point, capture=clock, resolved=version,
                                                  calendar=self.key, budget=self.base.budget)
                projected = self.projector.project(request)
                self.assertEqual((projected.date, projected.time), (anchor.origin.date, anchor.origin.time))
                self.assertEqual(projected.version, version.version)

        mixed = CalendarProjectionInput(point=historical_clock.point, capture=historical_clock, resolved=new_version,
                                        calendar=self.key, budget=self.base.budget)
        self.assertIsInstance(self.projector.project(mixed), CalendarSourceMismatch)

    def setUp(self):
        settings = custom_settings()
        self.key = settings.selected
        self.validator = make_calendar_validator()
        self.projector = make_calendar_projector()
        self.base = SettingsPreparationBase(
            operation_id="op", clock=TimeCapture(publication=publication(), point=point(9*3600)),
            budget=CalendarBudget(max_rule_checks=100, max_year_patterns=100),
            capture=TimeSettingsCapture(source=publication(), settings=settings, versions=(
                CalendarVersionRef(calendar_key=self.key, publication=publication()),)),
        )

    def next_base(self, proposal):
        versions = tuple(CalendarVersionRef(calendar_key=e.definition.system_calendar, publication=publication())
                         for e in proposal.after.calendars.entries)
        return self.base.model_copy(update={"capture": TimeSettingsCapture(
            source=publication(), settings=proposal.after, versions=versions)})

    def test_calendar_operations(self):
        from app.application.worldData.timeSettings.factory import make_calendar_settings_pipeline
        from app.dataModel.world.settings.timeOperations.changes import CalendarCreate, CalendarUpdate, CalendarSelect, CalendarRemove
        from app.dataModel.world.settings.timeOperations.results import SettingsInvalid
        pipeline = make_calendar_settings_pipeline(self.validator, self.projector)
        entry = self.base.capture.settings.calendars.entries[0]
        self.assertIsInstance(pipeline.prepare_calendar_create(CalendarCreate(base=self.base, entry=entry)), SettingsInvalid)
        key = RegistryKey("island")
        added = entry.model_copy(update={"definition": entry.definition.model_copy(update={"system_calendar":key})})
        created = pipeline.prepare_calendar_create(CalendarCreate(base=self.base, entry=added))
        base = self.next_base(created)
        selected = pipeline.prepare_calendar_select(CalendarSelect(base=base, calendar=key))
        self.assertEqual(selected.after.selected, key)
        updated = pipeline.prepare_calendar_update(CalendarUpdate(base=base, entry=added))
        self.assertEqual(updated.after.calendars.entry_for(key).anchor.origin.time.hour, 9)
        removed = pipeline.prepare_calendar_remove(CalendarRemove(base=self.next_base(selected), calendar=key, replacement=self.key))
        self.assertEqual(removed.after, self.base.capture.settings)

    def test_epoch_operations(self):
        from app.application.worldData.timeSettings.factory import make_epoch_settings_pipeline
        from app.dataModel.world.calendar.epochs.epoch import WorldCalendarEpoch
        from app.dataModel.world.settings.timeOperations.changes import EpochCreate, EpochUpdate, EpochRemove
        pipeline = make_epoch_settings_pipeline(self.validator)
        key = RegistryKey("reign")
        epoch = WorldCalendarEpoch(system_epoch=key, display_epoch="Reign", description="", calendar=self.key,
                                   start_seconds=0, start_nanoseconds=1, start_year_label=10)
        created = pipeline.prepare_epoch_create(EpochCreate(base=self.base, epoch=epoch))
        base = self.next_base(created)
        resolved = WorldCalendarResolver.resolve_at(ResolveCalendarAt(capture=base.capture, calendar=self.key))
        for p, label in ((point(), None), (point(0, 1), 10), (point(72000), 11)):
            result = self.projector.project(CalendarProjectionInput(point=p, capture=base.clock, calendar=self.key,
                                                                    resolved=resolved, budget=base.budget))
            self.assertEqual(result.epoch_year, label)
        updated = pipeline.prepare_epoch_update(EpochUpdate(base=base, epoch=epoch.model_copy(update={"start_year_label":15})))
        self.assertEqual(updated.after.epochs.entry_for(key).start_year_label, 15)
        removed = pipeline.prepare_epoch_remove(EpochRemove(base=self.next_base(updated), epoch=key))
        self.assertEqual(removed.after, self.base.capture.settings)

    def test_year_offset_and_revision(self):
        from app.dataModel.world.calendar.enums.rules import CalendarPredicateKind
        from app.dataModel.world.calendar.rules.predicates import YearModuloPredicate
        from app.dataModel.world.calendar.projection.errors import CalendarSourceMismatch
        from app.application.time.calendar.rules import matches
        rule = YearModuloPredicate(kind=CalendarPredicateKind.YEAR_MODULO, modulus=7, offset=2, residue=1)
        for year in (-11, -4, 3, 10):
            self.assertTrue(matches(rule, year))
            self.assertFalse(matches(rule, year+1))
        resolved = WorldCalendarResolver.resolve_at(ResolveCalendarAt(capture=self.base.capture, calendar=self.key))
        stale = self.base.clock.publication.model_copy(update={"publication_id":"other"})
        request = CalendarProjectionInput(point=point(), capture=self.base.clock, resolved=resolved.model_copy(
                    update={"source":stale}), calendar=self.key, budget=self.base.budget)
        self.assertIsInstance(self.projector.project(request), CalendarSourceMismatch)

class AdmissionTests(unittest.TestCase):
    def test_registry_identity_and_policy(self):
        from typing import get_type_hints
        from app.dataModel.registryKey import registry_key_target
        from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
        from app.dataModel.world.settings.timeOperations.initial import StandardTimeSettingsInput
        annotation = get_type_hints(WorldTimeSettings, include_extras=True)["selected"]
        self.assertIs(registry_key_target(annotation), WorldCalendarRegistry)
        self.assertEqual(StandardTimeSettingsInput.model_validate_json('{"kind":"standard"}').hours_per_day, 24)
        for value in (None, "", False, 0, "24"):
            with self.assertRaises(ValidationError):
                StandardTimeSettingsInput.model_validate_json(json.dumps({"kind":"standard", "hours_per_day":value}))
        data = custom_settings().model_dump(mode="json")
        entry = data["calendars"]["entries"][0]
        for bad_key in ("bad key", "A", "", "x-1"):
            entry["definition"]["system_calendar"] = bad_key
            with self.assertRaises(ValidationError):
                WorldTimeSettings.model_validate_json(json.dumps(data))

    def test_interval_and_proposal_invariants(self):
        from app.dataModel.time.changes.advance import TimeAdvanceProposal
        base = TimeCapture(publication=publication(), point=point())
        with self.assertRaises(ValidationError):
            TimeInterval(start=point(), end=point(timeline="other"))
        for start, end in ((point(), point()), (point(1), point(2))):
            with self.assertRaises(ValidationError):
                TimeAdvanceProposal(operation_id="op", base=base, interval=TimeInterval(start=start, end=end))
        with self.assertRaises(ValidationError):
            TimeCapture(publication=publication(), point=point(timeline="parent"))


class ReadPortTests(unittest.IsolatedAsyncioTestCase):
    async def test_pinned_reads(self):
        from asyncio import CancelledError
        from unittest.mock import create_autospec
        from app.application.time.composition.factory import make_time_reader
        from app.application.time.reads.sourcePort import ITimeReadSource
        from app.application.worldData.timeSettings.factory import make_world_settings_reader
        from app.application.worldData.timeSettings.sourcePort import IWorldTimeSettingsSource
        from app.dataModel.time.reads.capture import HistoricalTimeCapture
        from app.dataModel.time.reads.request import CurrentTimeRead, HistoricalTimeRead
        from app.dataModel.world.settings.timeOperations.read import HistoricalTimeSettingsRead, TimeSettingsRead
        from app.dataModel.world.settings.timeOperations.results import SettingsNotFound, SettingsSnapshotNotFound
        source = create_autospec(ITimeReadSource, instance=True)
        current = CurrentTimeRead(expected=publication())
        snapshot = current.expected.snapshot_head
        source.read_current.return_value = TimeCapture(publication=current.expected, point=point())
        reader = make_time_reader(source)
        self.assertEqual(await reader.read_current(current), source.read_current.return_value)
        source.read_current.assert_awaited_once_with(current)
        source.read_historical.return_value = HistoricalTimeCapture(snapshot=snapshot, point=point(timeline="parent"))
        historical = HistoricalTimeRead(snapshot=snapshot)
        self.assertEqual(await reader.read_historical(historical), source.read_historical.return_value)
        source.read_historical.assert_awaited_once_with(historical)
        source.read_current.side_effect = CancelledError
        with self.assertRaises(CancelledError):
            await reader.read_current(current)
        settings = create_autospec(IWorldTimeSettingsSource, instance=True)
        reader = make_world_settings_reader(settings)
        settings.read_current.return_value = SettingsNotFound(world_uid="world")
        settings.read_historical.return_value = SettingsSnapshotNotFound(snapshot=snapshot)
        self.assertEqual(await reader.read_current(TimeSettingsRead(expected=current.expected)), settings.read_current.return_value)
        self.assertEqual(await reader.read_historical(HistoricalTimeSettingsRead(snapshot=snapshot)), settings.read_historical.return_value)

class InitializationTests(unittest.TestCase):
    def prepare(self, authored, utc):
        from app.application.worldData.timeSettings.factory import make_initial_settings_pipeline
        from app.dataModel.world.settings.timeOperations.initial import PrepareInitialSettings
        request = PrepareInitialSettings(operation_id="initial", world_uid="world", input=authored,
                    captured_utc=utc, budget=CalendarBudget(max_year_patterns=400, max_rule_checks=800))
        return make_initial_settings_pipeline(make_calendar_validator()).prepare_initial(request)

    def test_standard(self):
        from app.dataModel.world.calendar.enums.rules import CalendarInitializationKind
        from app.dataModel.world.settings.timeOperations.initial import StandardTimeSettingsInput, InitialAnchorRequired
        from app.dataModel.world.settings.timeOperations.results import SettingsInvalid
        standard = StandardTimeSettingsInput(kind=CalendarInitializationKind.STANDARD)
        for utc, expected_day, expected_span, expected_weekday in [
            ("1900-02-28T18:20:00.123456Z", 1, "march", "wednesday"),
            ("2000-02-28T18:20:00.123456Z", 29, "february", "monday"),
            ("1970-01-01T18:20:00.123456Z", 2, "january", "thursday"),
        ]:
            settings = self.prepare(standard, utc).settings
            key = settings.selected
            version = CalendarVersionRef(calendar_key=key, publication=publication())
            capture = TimeSettingsCapture(source=publication(), settings=settings, versions=(version,))
            resolved = WorldCalendarResolver.resolve_at(ResolveCalendarAt(capture=capture, calendar=key))
            clock = TimeCapture(point=point(), publication=publication())
            request = CalendarProjectionInput(point=point(), capture=clock, calendar=key, resolved=resolved,
                                     budget=CalendarBudget(max_year_patterns=400, max_rule_checks=800))
            now = make_calendar_projector().project(request)
            self.assertEqual((now.weekday, now.season, now.period), (expected_weekday, "winter", "evening"))
            self.assertEqual(now.time.nanoseconds, 123456000)
            tomorrow = make_calendar_projector().project(request.model_copy(update={"point":point(86400)}))
            self.assertEqual((tomorrow.date.day, tomorrow.date.span), (expected_day, expected_span))
        short = standard.model_copy(update={"hours_per_day":10})
        self.assertIsInstance(self.prepare(short, utc), InitialAnchorRequired)
        settings = self.prepare(short, "1970-01-01T00:00:00.000000Z").settings
        periods = settings.calendars.entries[0].definition.periods.entries
        self.assertEqual([p.from_hour for p in periods], [0, 3, 5, 8])
        self.assertIsInstance(self.prepare(standard.model_copy(update={"hours_per_day":2}), utc), SettingsInvalid)

    def test_authored(self):
        from app.dataModel.world.calendar.enums.rules import CalendarInitializationKind
        from app.dataModel.world.settings.timeOperations.initial import AuthoredTimeSettingsInput
        authored = AuthoredTimeSettingsInput(kind=CalendarInitializationKind.AUTHORED, settings=custom_settings())
        result = self.prepare(authored, "2026-11-03T18:20:00.000000Z")
        self.assertEqual(result.settings, authored.settings)
