"""Select one engine CALL for Time settings preparation."""

import asyncio
from dataclasses import dataclass

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.invocation.callTarget import CallTarget
from app.application.engine.contracts.invocation.nodeStep import Call, Complete, NodeStep
from app.application.engine.contracts.invocation.resumeEvent import CallCancelled, CallFailure, CallResults, CallRuntimeFailure, CallSuccess, ResumeEvent
from app.application.engine.nodeTypes.resumablePythonNode import ResumablePythonNode
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.identity import CallKey, ContractId, ContractVersion, NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    TimeSettingsNodeError,
    PrepareHoursChangeInput, PrepareHoursChangeOutput,
    PrepareCalendarCreateInput, PrepareCalendarCreateOutput,
    PrepareCalendarUpdateInput, PrepareCalendarUpdateOutput,
    PrepareCalendarSelectInput, PrepareCalendarSelectOutput,
    PrepareCalendarRemoveInput, PrepareCalendarRemoveOutput,
    PrepareEpochCreateInput, PrepareEpochCreateOutput,
    PrepareEpochUpdateInput, PrepareEpochUpdateOutput,
    PrepareEpochRemoveInput, PrepareEpochRemoveOutput,
)
from app.dataModel.engine.nodes.timeSettingsWorkflowContracts import (
    PrepareTimeSettingsBatchInput, PrepareTimeSettingsBatchOutput,
    PrepareWorldTimeSettingsChangesInput, PrepareWorldTimeSettingsChangesOutput,
)
from app.dataModel.world.settings.timeOperations.changes import (
    HoursChange,
    CalendarCreate,
    CalendarUpdate,
    CalendarSelect,
    CalendarRemove,
    EpochCreate,
    EpochUpdate,
    EpochRemove,
)

CALL_KEY = CallKey("settings_preparation")

HOURS_CHANGE_TARGET = CallTarget[PrepareHoursChangeInput, PrepareHoursChangeOutput, TimeSettingsNodeError](
    NodeId("prepare_hours_change"), ContractId("engine.time.settings.prepare_hours_change"), ContractVersion("1"),
    PrepareHoursChangeInput, PrepareHoursChangeOutput, (TimeSettingsNodeError,),
)

CALENDAR_CREATE_TARGET = CallTarget[PrepareCalendarCreateInput, PrepareCalendarCreateOutput, TimeSettingsNodeError](
    NodeId("prepare_calendar_create"), ContractId("engine.time.settings.prepare_calendar_create"), ContractVersion("1"),
    PrepareCalendarCreateInput, PrepareCalendarCreateOutput, (TimeSettingsNodeError,),
)

CALENDAR_UPDATE_TARGET = CallTarget[PrepareCalendarUpdateInput, PrepareCalendarUpdateOutput, TimeSettingsNodeError](
    NodeId("prepare_calendar_update"), ContractId("engine.time.settings.prepare_calendar_update"), ContractVersion("1"),
    PrepareCalendarUpdateInput, PrepareCalendarUpdateOutput, (TimeSettingsNodeError,),
)

CALENDAR_SELECT_TARGET = CallTarget[PrepareCalendarSelectInput, PrepareCalendarSelectOutput, TimeSettingsNodeError](
    NodeId("prepare_calendar_select"), ContractId("engine.time.settings.prepare_calendar_select"), ContractVersion("1"),
    PrepareCalendarSelectInput, PrepareCalendarSelectOutput, (TimeSettingsNodeError,),
)

CALENDAR_REMOVE_TARGET = CallTarget[PrepareCalendarRemoveInput, PrepareCalendarRemoveOutput, TimeSettingsNodeError](
    NodeId("prepare_calendar_remove"), ContractId("engine.time.settings.prepare_calendar_remove"), ContractVersion("1"),
    PrepareCalendarRemoveInput, PrepareCalendarRemoveOutput, (TimeSettingsNodeError,),
)

EPOCH_CREATE_TARGET = CallTarget[PrepareEpochCreateInput, PrepareEpochCreateOutput, TimeSettingsNodeError](
    NodeId("prepare_epoch_create"), ContractId("engine.time.settings.prepare_epoch_create"), ContractVersion("1"),
    PrepareEpochCreateInput, PrepareEpochCreateOutput, (TimeSettingsNodeError,),
)

EPOCH_UPDATE_TARGET = CallTarget[PrepareEpochUpdateInput, PrepareEpochUpdateOutput, TimeSettingsNodeError](
    NodeId("prepare_epoch_update"), ContractId("engine.time.settings.prepare_epoch_update"), ContractVersion("1"),
    PrepareEpochUpdateInput, PrepareEpochUpdateOutput, (TimeSettingsNodeError,),
)

EPOCH_REMOVE_TARGET = CallTarget[PrepareEpochRemoveInput, PrepareEpochRemoveOutput, TimeSettingsNodeError](
    NodeId("prepare_epoch_remove"), ContractId("engine.time.settings.prepare_epoch_remove"), ContractVersion("1"),
    PrepareEpochRemoveInput, PrepareEpochRemoveOutput, (TimeSettingsNodeError,),
)

BATCH_TARGET = CallTarget[PrepareTimeSettingsBatchInput, PrepareTimeSettingsBatchOutput, TimeSettingsNodeError](
    NodeId("prepare_time_settings_batch"), ContractId("engine.time.settings.prepare_time_settings_batch"),
    ContractVersion("1"), PrepareTimeSettingsBatchInput, PrepareTimeSettingsBatchOutput, (),
)

SETTINGS_CALLS = (
    HOURS_CHANGE_TARGET,
    CALENDAR_CREATE_TARGET,
    CALENDAR_UPDATE_TARGET,
    CALENDAR_SELECT_TARGET,
    CALENDAR_REMOVE_TARGET,
    EPOCH_CREATE_TARGET,
    EPOCH_UPDATE_TARGET,
    EPOCH_REMOVE_TARGET,
    BATCH_TARGET,
)


@dataclass(frozen=True, kw_only=True)
class PrepareWorldTimeSettingsChangesNode(ResumablePythonNode[
    PrepareWorldTimeSettingsChangesInput, PrepareWorldTimeSettingsChangesOutput,
    TimeSettingsNodeError, PrepareWorldTimeSettingsChangesInput,
]):
    id: NodeId = NodeId("prepare_world_time_settings_changes")
    skip_on_replan: bool = False

    async def prepare_input(self, view: DAGReadView) -> PrepareWorldTimeSettingsChangesInput:
        raise RuntimeError("prepare_world_time_settings_changes requires explicit invocation input")

    async def start(self, input: PrepareWorldTimeSettingsChangesInput) -> NodeStep[PrepareWorldTimeSettingsChangesOutput, PrepareWorldTimeSettingsChangesInput]:
        commands = input.request.commands
        if len(commands) > 1:
            return Call(CALL_KEY, BATCH_TARGET, PrepareTimeSettingsBatchInput(request=input.request), input)
        command = commands[0]
        if isinstance(command, HoursChange):
            return Call(CALL_KEY, HOURS_CHANGE_TARGET, PrepareHoursChangeInput(request=command), input)
        if isinstance(command, CalendarCreate):
            return Call(CALL_KEY, CALENDAR_CREATE_TARGET, PrepareCalendarCreateInput(request=command), input)
        if isinstance(command, CalendarUpdate):
            return Call(CALL_KEY, CALENDAR_UPDATE_TARGET, PrepareCalendarUpdateInput(request=command), input)
        if isinstance(command, CalendarSelect):
            return Call(CALL_KEY, CALENDAR_SELECT_TARGET, PrepareCalendarSelectInput(request=command), input)
        if isinstance(command, CalendarRemove):
            return Call(CALL_KEY, CALENDAR_REMOVE_TARGET, PrepareCalendarRemoveInput(request=command), input)
        if isinstance(command, EpochCreate):
            return Call(CALL_KEY, EPOCH_CREATE_TARGET, PrepareEpochCreateInput(request=command), input)
        if isinstance(command, EpochUpdate):
            return Call(CALL_KEY, EPOCH_UPDATE_TARGET, PrepareEpochUpdateInput(request=command), input)
        if isinstance(command, EpochRemove):
            return Call(CALL_KEY, EPOCH_REMOVE_TARGET, PrepareEpochRemoveInput(request=command), input)
        raise TypeError("unsupported Time settings command")

    async def resume(self, state: PrepareWorldTimeSettingsChangesInput, event: ResumeEvent) -> NodeStep[PrepareWorldTimeSettingsChangesOutput, PrepareWorldTimeSettingsChangesInput]:
        if not isinstance(event, CallResults):
            raise TypeError("Time settings preparation requires a CALL result")
        if len(state.request.commands) > 1:
            result = event.get(CALL_KEY, BATCH_TARGET)
        else:
            command = state.request.commands[0]
            if isinstance(command, HoursChange):
                result = event.get(CALL_KEY, HOURS_CHANGE_TARGET)
            elif isinstance(command, CalendarCreate):
                result = event.get(CALL_KEY, CALENDAR_CREATE_TARGET)
            elif isinstance(command, CalendarUpdate):
                result = event.get(CALL_KEY, CALENDAR_UPDATE_TARGET)
            elif isinstance(command, CalendarSelect):
                result = event.get(CALL_KEY, CALENDAR_SELECT_TARGET)
            elif isinstance(command, CalendarRemove):
                result = event.get(CALL_KEY, CALENDAR_REMOVE_TARGET)
            elif isinstance(command, EpochCreate):
                result = event.get(CALL_KEY, EPOCH_CREATE_TARGET)
            elif isinstance(command, EpochUpdate):
                result = event.get(CALL_KEY, EPOCH_UPDATE_TARGET)
            elif isinstance(command, EpochRemove):
                result = event.get(CALL_KEY, EPOCH_REMOVE_TARGET)
            else:
                raise TypeError("unsupported Time settings command")
        if isinstance(result, CallSuccess):
            return Complete(PrepareWorldTimeSettingsChangesOutput(value=result.output.value))
        if isinstance(result, CallFailure):
            raise PythonNodeError(result.error)
        if isinstance(result, CallCancelled):
            raise asyncio.CancelledError
        if isinstance(result, CallRuntimeFailure):
            raise RuntimeError("Time settings child CALL failed")
        raise TypeError("unknown Time settings CALL result")
