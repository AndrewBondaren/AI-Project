from .shared.context import CandidatePreparation
from .algorithms.calendar import calendar_create, calendar_update, calendar_select, calendar_remove
from app.application.time.calendar.validation import CalendarValidator
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from app.application.time.calendar.projection import CalendarProjector
from app.dataModel.world.settings.timeOperations.results import SettingsAnchorRequired
from app.dataModel.world.settings.timeOperations.changes import CalendarCreate, CalendarUpdate, CalendarSelect, CalendarRemove
from app.dataModel.world.settings.timeOperations.results import SettingsInUse


class WorldCalendarSettingsPipelineOpenPipeline:
    def __init__(self, validator: CalendarValidator, projector: CalendarProjector):
        self._validator = validator
        self._projector = projector

    def prepare_calendar_create(self, request: CalendarCreate) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        request = CalendarCreate.model_validate(request, strict=True)
        return calendar_create(request, CandidatePreparation(request.base, request.base.capture.settings, self._validator, self._projector))

    def prepare_calendar_update(self, request: CalendarUpdate) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired:
        request = CalendarUpdate.model_validate(request, strict=True)
        return calendar_update(request, CandidatePreparation(request.base, request.base.capture.settings, self._validator, self._projector))

    def prepare_calendar_select(self, request: CalendarSelect) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        request = CalendarSelect.model_validate(request, strict=True)
        return calendar_select(request, CandidatePreparation(request.base, request.base.capture.settings, self._validator, self._projector))

    def prepare_calendar_remove(self, request: CalendarRemove) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsInUse:
        request = CalendarRemove.model_validate(request, strict=True)
        return calendar_remove(request, CandidatePreparation(request.base, request.base.capture.settings, self._validator, self._projector))
