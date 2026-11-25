"""Transport for Time settings workflow operations."""

from app.dataModel.world.calendar.scalars import CalendarRecord
from app.dataModel.world.settings.timeOperations.batch import PrepareTimeSettingsBatch, SettingsBatchInputMismatch, SettingsBatchRefused
from app.dataModel.world.settings.timeOperations.results import PreparedTimeSettingsChange
from app.dataModel.world.settings.timeOperations.results import SettingsInvalid, SettingsAnchorRequired, SettingsInUse
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from app.dataModel.world.settings.timePublication.section import PrepareTimeSettingsSection, WorldTimeSettingsSection
from app.dataModel.world.settings.timePublication.errors import SettingsSectionContextMismatch


class PrepareTimeSettingsBatchInput(CalendarRecord):
    request: PrepareTimeSettingsBatch


class PrepareTimeSettingsBatchOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsBatchInputMismatch | SettingsBatchRefused


class PrepareTimeSettingsSectionInput(CalendarRecord):
    request: PrepareTimeSettingsSection


class PrepareTimeSettingsSectionOutput(CalendarRecord):
    value: WorldTimeSettingsSection | SettingsSectionContextMismatch


class PrepareWorldTimeSettingsChangesInput(CalendarRecord):
    request: PrepareTimeSettingsBatch


class PrepareWorldTimeSettingsChangesOutput(CalendarRecord):
    value: PreparedTimeSettingsChange | SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired | SettingsInUse | SettingsBatchInputMismatch | SettingsBatchRefused
