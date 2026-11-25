"""Explicit Time settings operation registrations."""
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.nodes.time.timeSettings.prepareHoursChangeNode import PrepareHoursChangeNode
from app.application.engine.nodes.time.timeSettings.prepareCalendarCreateNode import PrepareCalendarCreateNode
from app.application.engine.nodes.time.timeSettings.prepareCalendarUpdateNode import PrepareCalendarUpdateNode
from app.application.engine.nodes.time.timeSettings.prepareCalendarSelectNode import PrepareCalendarSelectNode
from app.application.engine.nodes.time.timeSettings.prepareCalendarRemoveNode import PrepareCalendarRemoveNode
from app.application.engine.nodes.time.timeSettings.prepareEpochCreateNode import PrepareEpochCreateNode
from app.application.engine.nodes.time.timeSettings.prepareEpochUpdateNode import PrepareEpochUpdateNode
from app.application.engine.nodes.time.timeSettings.prepareEpochRemoveNode import PrepareEpochRemoveNode
from app.application.engine.nodes.time.timeSettings.prepareTimeSettingsBatchNode import PrepareTimeSettingsBatchNode
from app.application.engine.nodes.time.timeSettings.prepareTimeSettingsSectionNode import PrepareTimeSettingsSectionNode
from app.application.engine.nodes.time.timeSettings.prepareWorldTimeSettingsChangesNode import PrepareWorldTimeSettingsChangesNode, SETTINGS_CALLS
from app.application.engine.contracts.invocation.continuationContract import ContinuationContract
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.dataModel.engine.dag.identity import ContractId, ContractVersion
from app.dataModel.engine.nodes.timeSettingsContracts import TimeSettingsNodeError, PrepareHoursChangeInput, PrepareHoursChangeOutput, PrepareCalendarCreateInput, PrepareCalendarCreateOutput, PrepareCalendarUpdateInput, PrepareCalendarUpdateOutput, PrepareCalendarSelectInput, PrepareCalendarSelectOutput, PrepareCalendarRemoveInput, PrepareCalendarRemoveOutput, PrepareEpochCreateInput, PrepareEpochCreateOutput, PrepareEpochUpdateInput, PrepareEpochUpdateOutput, PrepareEpochRemoveInput, PrepareEpochRemoveOutput
from app.dataModel.engine.nodes.timeSettingsWorkflowContracts import PrepareTimeSettingsBatchInput, PrepareTimeSettingsBatchOutput, PrepareTimeSettingsSectionInput, PrepareTimeSettingsSectionOutput, PrepareWorldTimeSettingsChangesInput, PrepareWorldTimeSettingsChangesOutput
from typing import Never

PREPARE_TIME_SETTINGS_BATCH_CONTRACT = NodeContract[PrepareTimeSettingsBatchInput, PrepareTimeSettingsBatchOutput, Never](
    input_type=PrepareTimeSettingsBatchInput, output_type=PrepareTimeSettingsBatchOutput,
    contract_id=ContractId("engine.time.settings.prepare_time_settings_batch"),
    version=ContractVersion("1"), reads=(), calls=(), error_types=(),
)

PREPARE_TIME_SETTINGS_SECTION_CONTRACT = NodeContract[PrepareTimeSettingsSectionInput, PrepareTimeSettingsSectionOutput, Never](
    input_type=PrepareTimeSettingsSectionInput, output_type=PrepareTimeSettingsSectionOutput,
    contract_id=ContractId("engine.time.settings.prepare_time_settings_section"),
    version=ContractVersion("1"), reads=(), calls=(), error_types=(),
)

PREPARE_WORLD_TIME_SETTINGS_CHANGES_CONTRACT = NodeContract[
    PrepareWorldTimeSettingsChangesInput, PrepareWorldTimeSettingsChangesOutput, TimeSettingsNodeError,
](
    input_type=PrepareWorldTimeSettingsChangesInput,
    output_type=PrepareWorldTimeSettingsChangesOutput,
    contract_id=ContractId("engine.time.settings.prepare_world_time_settings_changes"),
    version=ContractVersion("1"), reads=(), calls=SETTINGS_CALLS,
    continuation=ContinuationContract(ContractId("engine.time.settings.prepare_world_time_settings_changes.state"), ContractVersion("1"), PrepareWorldTimeSettingsChangesInput),
    error_types=(TimeSettingsNodeError,),
)

PREPARE_HOURS_CHANGE_CONTRACT = NodeContract(
    input_type=PrepareHoursChangeInput,
    output_type=PrepareHoursChangeOutput,
    contract_id=ContractId("engine.time.settings.prepare_hours_change"),
    version=ContractVersion("1"), reads=(), error_types=(TimeSettingsNodeError,),
)

PREPARE_CALENDAR_CREATE_CONTRACT = NodeContract(
    input_type=PrepareCalendarCreateInput,
    output_type=PrepareCalendarCreateOutput,
    contract_id=ContractId("engine.time.settings.prepare_calendar_create"),
    version=ContractVersion("1"), reads=(), error_types=(TimeSettingsNodeError,),
)

PREPARE_CALENDAR_UPDATE_CONTRACT = NodeContract(
    input_type=PrepareCalendarUpdateInput,
    output_type=PrepareCalendarUpdateOutput,
    contract_id=ContractId("engine.time.settings.prepare_calendar_update"),
    version=ContractVersion("1"), reads=(), error_types=(TimeSettingsNodeError,),
)

PREPARE_CALENDAR_SELECT_CONTRACT = NodeContract(
    input_type=PrepareCalendarSelectInput,
    output_type=PrepareCalendarSelectOutput,
    contract_id=ContractId("engine.time.settings.prepare_calendar_select"),
    version=ContractVersion("1"), reads=(), error_types=(TimeSettingsNodeError,),
)

PREPARE_CALENDAR_REMOVE_CONTRACT = NodeContract(
    input_type=PrepareCalendarRemoveInput,
    output_type=PrepareCalendarRemoveOutput,
    contract_id=ContractId("engine.time.settings.prepare_calendar_remove"),
    version=ContractVersion("1"), reads=(), error_types=(TimeSettingsNodeError,),
)

PREPARE_EPOCH_CREATE_CONTRACT = NodeContract(
    input_type=PrepareEpochCreateInput,
    output_type=PrepareEpochCreateOutput,
    contract_id=ContractId("engine.time.settings.prepare_epoch_create"),
    version=ContractVersion("1"), reads=(), error_types=(TimeSettingsNodeError,),
)

PREPARE_EPOCH_UPDATE_CONTRACT = NodeContract(
    input_type=PrepareEpochUpdateInput,
    output_type=PrepareEpochUpdateOutput,
    contract_id=ContractId("engine.time.settings.prepare_epoch_update"),
    version=ContractVersion("1"), reads=(), error_types=(TimeSettingsNodeError,),
)

PREPARE_EPOCH_REMOVE_CONTRACT = NodeContract(
    input_type=PrepareEpochRemoveInput,
    output_type=PrepareEpochRemoveOutput,
    contract_id=ContractId("engine.time.settings.prepare_epoch_remove"),
    version=ContractVersion("1"), reads=(), error_types=(TimeSettingsNodeError,),
)

def register_time_settings_nodes(registry: NodeRegistry) -> None:
    registry.register_python(PrepareTimeSettingsBatchNode, PythonNodeExecutor, PREPARE_TIME_SETTINGS_BATCH_CONTRACT)
    registry.register_python(PrepareTimeSettingsSectionNode, PythonNodeExecutor, PREPARE_TIME_SETTINGS_SECTION_CONTRACT)
    registry.register_resumable(PrepareWorldTimeSettingsChangesNode, PythonNodeExecutor, PREPARE_WORLD_TIME_SETTINGS_CHANGES_CONTRACT)
    registry.register_python(PrepareHoursChangeNode, PythonNodeExecutor, PREPARE_HOURS_CHANGE_CONTRACT)
    registry.register_python(PrepareCalendarCreateNode, PythonNodeExecutor, PREPARE_CALENDAR_CREATE_CONTRACT)
    registry.register_python(PrepareCalendarUpdateNode, PythonNodeExecutor, PREPARE_CALENDAR_UPDATE_CONTRACT)
    registry.register_python(PrepareCalendarSelectNode, PythonNodeExecutor, PREPARE_CALENDAR_SELECT_CONTRACT)
    registry.register_python(PrepareCalendarRemoveNode, PythonNodeExecutor, PREPARE_CALENDAR_REMOVE_CONTRACT)
    registry.register_python(PrepareEpochCreateNode, PythonNodeExecutor, PREPARE_EPOCH_CREATE_CONTRACT)
    registry.register_python(PrepareEpochUpdateNode, PythonNodeExecutor, PREPARE_EPOCH_UPDATE_CONTRACT)
    registry.register_python(PrepareEpochRemoveNode, PythonNodeExecutor, PREPARE_EPOCH_REMOVE_CONTRACT)
