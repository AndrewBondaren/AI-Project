"""Explicit registration for the Time section leaf."""

from typing import Never

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.nodes.time.prepareTimeSectionNode import PrepareTimeSectionNode
from app.application.engine.nodes.time.timeSettings.registration import register_time_settings_nodes
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.dataModel.engine.dag.identity import ContractId, ContractVersion
from app.dataModel.engine.nodes.time.contracts import PrepareTimeSectionInput, PrepareTimeSectionOutput


PREPARE_TIME_SECTION_CONTRACT = NodeContract[PrepareTimeSectionInput, PrepareTimeSectionOutput, Never](
    input_type=PrepareTimeSectionInput,
    output_type=PrepareTimeSectionOutput,
    contract_id=ContractId("engine.time.prepare_time_section"),
    version=ContractVersion("1"),
    reads=(),
    calls=(),
    error_types=(),
)


def register_time_nodes(registry: NodeRegistry) -> None:
    registry.register_python(PrepareTimeSectionNode, PythonNodeExecutor, PREPARE_TIME_SECTION_CONTRACT)
    register_time_settings_nodes(registry)
