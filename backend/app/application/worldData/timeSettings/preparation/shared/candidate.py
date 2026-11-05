from app.dataModel.world.settings.timeOperations.results import SettingsInvalid
from pydantic import BaseModel
from app.dataModel.world.calendar.projection.errors import CalendarFieldIssue, CalendarIssueCode
from app.application.time.calendar.projection import CalendarProjector
from app.application.time.calendar.validation import CalendarValidator
from app.dataModel.world.calendar.projection.request import CalendarProjectionInput, ValidateCalendarInput
from app.dataModel.world.calendar.projection.result import CalendarProjection
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded, CalendarInvalid
from app.dataModel.world.calendar.definitions.registry import WorldCalendarRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.world.settings.timeSettings import WorldTimeSettings
from app.dataModel.world.settings.timeOperations.changes import SettingsPreparationBase
from app.dataModel.world.settings.timeOperations.read import ResolveCalendarAt
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange
from ...reader import WorldCalendarResolver


def issue(request: BaseModel, field: str, message: str) -> SettingsInvalid:
    return SettingsInvalid(issues=(CalendarFieldIssue.at(type(request), tuple(field.split(".")), CalendarIssueCode.INVALID_SETTINGS_CHANGE, message),))


def projected(base: SettingsPreparationBase, key: RegistryKey[WorldCalendarRegistry], projector: CalendarProjector) -> CalendarProjection | SettingsInvalid | CalendarBudgetExceeded:
    resolved = WorldCalendarResolver.resolve_at(ResolveCalendarAt(capture=base.capture, calendar=key))
    if isinstance(resolved, SettingsInvalid):
        return resolved
    result = projector.project(CalendarProjectionInput(point=base.clock.point, capture=base.clock,
                               calendar=key, resolved=resolved, budget=base.budget))
    if isinstance(result, (CalendarProjection, CalendarBudgetExceeded)):
        return result
    if isinstance(result, CalendarInvalid):
        return SettingsInvalid(issues=result.issues)
    return issue(base, "capture", "inconsistent projection source")


def prepare(base: SettingsPreparationBase, candidate: WorldTimeSettings, validator: CalendarValidator) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
    result = validator.validate(ValidateCalendarInput(settings=candidate, budget=base.budget))
    if isinstance(result, CalendarBudgetExceeded):
        return result
    if isinstance(result, CalendarInvalid):
        return SettingsInvalid(issues=result.issues)
    return PreparedTimeSettingsChange(operation_id=base.operation_id, expected=base.capture.source,
                                      before=base.capture.settings, after=candidate, effective_at=base.clock.point)
