from typing import Annotated, Self

from pydantic import Field, StrictInt, model_validator

from app.dataModel.world.calendar.scalars import CalendarRecord
from app.dataModel.world.calendar.projection.errors import CalendarBudgetExceeded
from .changes import HoursChange, CalendarCreate, CalendarUpdate, CalendarSelect, CalendarRemove, EpochCreate, EpochUpdate, EpochRemove
from .results import SettingsInvalid, SettingsAnchorRequired, SettingsInUse


class PrepareTimeSettingsBatch(CalendarRecord):
    commands: tuple[HoursChange | CalendarCreate | CalendarUpdate | CalendarSelect | CalendarRemove |
                    EpochCreate | EpochUpdate | EpochRemove, ...] = Field(min_length=1)


class SettingsBatchInputMismatch(CalendarRecord):
    request: PrepareTimeSettingsBatch
    indices: tuple[Annotated[StrictInt, Field(ge=0)], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def exact_indices(self) -> Self:
        base = self.request.commands[0].base
        expected = tuple(i for i, command in enumerate(self.request.commands) if command.base != base)
        if self.indices != expected:
            raise ValueError("indices must identify all mismatching original command bases")
        return self


class SettingsBatchRefused(CalendarRecord):
    command_index: Annotated[StrictInt, Field(ge=0)]
    reason: SettingsInvalid | CalendarBudgetExceeded | SettingsAnchorRequired | SettingsInUse
