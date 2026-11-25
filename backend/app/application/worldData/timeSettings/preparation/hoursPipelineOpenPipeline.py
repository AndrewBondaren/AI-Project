from .shared.context import CandidatePreparation
from .algorithms.hours import hours_change
from app.application.time.calendar.validation import CalendarValidator
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from app.application.time.calendar.projection import CalendarProjector
from app.dataModel.world.settings.timeOperations.results import SettingsAnchorRequired
from app.dataModel.world.settings.timeOperations.changes import HoursChange


class WorldHoursSettingsPipelineOpenPipeline:
    def __init__(self, validator: CalendarValidator, projector: CalendarProjector):
        self._validator = validator
        self._projector = projector

    def prepare_hours_change(self, request: HoursChange) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired:
        request = HoursChange.model_validate(request, strict=True)
        return hours_change(request, CandidatePreparation(request.base, request.base.capture.settings, self._validator, self._projector))
