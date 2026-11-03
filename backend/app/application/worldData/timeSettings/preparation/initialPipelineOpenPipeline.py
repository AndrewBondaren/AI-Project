from datetime import datetime

from app.application.time.calendar.validation import CalendarValidator
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded, CalendarInvalid
from app.dataModel.world.calendar.projection.request import ValidateCalendarInput
from app.dataModel.world.settings.standard.gregorian import origin_from_utc
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from app.dataModel.world.settings.timeOperations.initial import (
    AuthoredTimeSettingsInput, InitialAnchorRequired, PrepareInitialSettings, PreparedInitialSettings,
)
from app.dataModel.world.settings.timeOperations.results import SettingsInvalid
from .shared.candidate import issue


class WorldInitialTimeSettingsPipelineOpenPipeline:
    def __init__(self, validator: CalendarValidator):
        self._validator = validator

    def prepare_initial(self, request: PrepareInitialSettings) -> PreparedInitialSettings | SettingsInvalid | InitialAnchorRequired | CalendarBudgetExceeded:
        authored = request.input
        if isinstance(authored, AuthoredTimeSettingsInput):
            settings = authored.settings
        else:
            if authored.hours_per_day < 4:
                return issue("hours_per_day", "standard period definitions require at least four hours")
            origin = authored.origin
            if origin is None:
                instant = datetime.strptime(request.captured_utc, "%Y-%m-%dT%H:%M:%S.%fZ")
                if instant.hour >= authored.hours_per_day:
                    return InitialAnchorRequired(hours_per_day=authored.hours_per_day, captured_hour=instant.hour)
                origin = origin_from_utc(instant)
            settings = WorldTimeSettings.standard(authored.hours_per_day, origin)
        result = self._validator.validate(ValidateCalendarInput(settings=settings, budget=request.budget))
        if isinstance(result, CalendarBudgetExceeded):
            return result
        if isinstance(result, CalendarInvalid):
            return SettingsInvalid(issues=result.issues)
        return PreparedInitialSettings(operation_id=request.operation_id, world_uid=request.world_uid,
                                      captured_utc=request.captured_utc, settings=settings)
