from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange, SettingsInvalid
from ..shared.candidate import issue
from app.dataModel.world.calendar.epochs.registry import WorldCalendarEpochRegistry
from app.dataModel.world.settings.timeOperations.changes import EpochCreate, EpochUpdate, EpochRemove


from ..shared.context import CandidatePreparation


def epoch_create(request: EpochCreate, context: CandidatePreparation) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
    settings = context.settings
    entries = settings.epochs.entries
    key = request.epoch.system_epoch
    if any(e.system_epoch == key for e in entries):
        return issue(CheckedPath.root(EpochCreate).field(FieldRef(lambda: EpochCreate, lambda value: value.epoch)), "epoch already exists")
    registry = WorldCalendarEpochRegistry(entries=(*entries, request.epoch))
    return context.prepare(settings.model_copy(update={"epochs": registry}))


def epoch_update(request: EpochUpdate, context: CandidatePreparation) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
    settings = context.settings
    entries = settings.epochs.entries
    key = request.epoch.system_epoch
    if not any(e.system_epoch == key for e in entries):
        return issue(CheckedPath.root(EpochUpdate).field(FieldRef(lambda: EpochUpdate, lambda value: value.epoch)), "unknown epoch")
    registry = WorldCalendarEpochRegistry(entries=tuple(request.epoch if e.system_epoch == key else e for e in entries))
    return context.prepare(settings.model_copy(update={"epochs": registry}))


def epoch_remove(request: EpochRemove, context: CandidatePreparation) -> PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded:
    settings = context.settings
    entries = settings.epochs.entries
    key = request.epoch
    if not any(e.system_epoch == key for e in entries):
        return issue(CheckedPath.root(EpochRemove).field(FieldRef(lambda: EpochRemove, lambda value: value.epoch)), "unknown epoch")
    registry = WorldCalendarEpochRegistry(entries=tuple(e for e in entries if e.system_epoch != key))
    return context.prepare(settings.model_copy(update={"epochs": registry}))

