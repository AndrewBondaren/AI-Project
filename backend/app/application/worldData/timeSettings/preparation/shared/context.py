"""One candidate calculation, with optional shared work for ordered preparation."""
from dataclasses import dataclass

from app.application.time.calendar.projection import CalendarProjector, coordinate_origin
from app.application.time.calendar.rules import Work, ExhaustedBudget, InvalidCalendar
from app.application.time.calendar.validation import CalendarValidator, validated_indexes, invalid
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.world.calendar.dates.anchor import CalendarOrigin
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded, CalendarFieldIssue
from app.dataModel.world.calendar.projection.result import CalendarProjection
from app.dataModel.world.settings.timeOperations.changes import SettingsPreparationBase
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from .candidate import projected, prepare, issue


@dataclass
class CandidatePreparation:
    base: SettingsPreparationBase
    settings: WorldTimeSettings
    validator: CalendarValidator | None = None
    projector: CalendarProjector | None = None
    work: Work | None = None

    def project(self, key: RegistryKey[WorldCalendarRegistry]) -> CalendarOrigin | CalendarProjection | SettingsInvalid | CalendarBudgetExceeded:
        if self.work is None:
            if self.projector is None:
                raise TypeError("projection dependency is required")
            return projected(self.base, key, self.projector)
        entry = self.settings.calendars.entry_for(key)
        if entry is None:
            return issue(CheckedPath.root(WorldTimeSettings).field(
                FieldRef(lambda: WorldTimeSettings, lambda value: value.calendars)), "unknown calendar")
        try:
            index = validated_indexes(self.settings, self.base.budget, work=self.work)[key]
            return coordinate_origin(entry, index, self.settings.hours_per_day, self.base.clock.point)[0]
        except ExhaustedBudget:
            return CalendarBudgetExceeded(budget=self.base.budget)
        except InvalidCalendar as error:
            return SettingsInvalid(issues=invalid(error).issues)

    def prepare(self, candidate: WorldTimeSettings) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        candidate = WorldTimeSettings.model_validate(candidate, strict=True)
        if self.work is None:
            if self.validator is None:
                raise TypeError("validation dependency is required")
            return prepare(self.base, candidate, self.validator)
        issues = ValidatorAggregationHelper((CalendarFieldIssue,))
        try:
            validated_indexes(candidate, self.base.budget, issues, work=self.work)
        except ExhaustedBudget:
            return CalendarBudgetExceeded(budget=self.base.budget)
        except InvalidCalendar as error:
            return SettingsInvalid(issues=invalid(error).issues)
        if facts := issues.snapshot():
            return SettingsInvalid(issues=facts)
        return PreparedTimeSettingsChange(operation_id=self.base.operation_id, expected=self.base.capture.source,
            before=self.base.capture.settings, after=candidate, effective_at=self.base.clock.point)
