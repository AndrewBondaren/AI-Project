from .shared.context import CandidatePreparation
from .algorithms.epoch import epoch_create, epoch_update, epoch_remove
from app.application.time.calendar.validation import CalendarValidator
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from app.dataModel.world.settings.timeOperations.changes import EpochCreate, EpochUpdate, EpochRemove


class WorldEpochSettingsPipelineOpenPipeline:
    def __init__(self, validator: CalendarValidator):
        self._validator = validator

    def prepare_epoch_create(self, request: EpochCreate) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        request = EpochCreate.model_validate(request, strict=True)
        return epoch_create(request, CandidatePreparation(request.base, request.base.capture.settings, self._validator))

    def prepare_epoch_update(self, request: EpochUpdate) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        request = EpochUpdate.model_validate(request, strict=True)
        return epoch_update(request, CandidatePreparation(request.base, request.base.capture.settings, self._validator))

    def prepare_epoch_remove(self, request: EpochRemove) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
        request = EpochRemove.model_validate(request, strict=True)
        return epoch_remove(request, CandidatePreparation(request.base, request.base.capture.settings, self._validator))
