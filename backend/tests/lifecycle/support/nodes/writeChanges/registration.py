"""Explicit mock-only write orchestrator registrations."""

from typing import Never

from app.application.engine.contracts.invocation.continuationContract import ContinuationContract
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.dataModel.engine.dag.identity import ContractId, ContractVersion
from tests.lifecycle.support.nodes.writeChanges.prepareChangesNode import PrepareChangesNode, SECTION_TARGET
from tests.lifecycle.support.nodes.writeChanges.writeChangesNode import WriteChangesNode, PREPARE_TARGET, ASSEMBLE_TARGET, APPLY_TARGET
from tests.lifecycle.support.writeChangesContracts import MockPrepareChangesInput, MockPrepareChangesOutput, MockWriteChangesInput, MockWriteChangesOutput, MockWriteChangesState
from tests.lifecycle.support.writeNodeContracts import SnapshotOperationCancelledNodeError, SnapshotPublicNodeError

PREPARE_CHANGES_CONTRACT: NodeContract[MockPrepareChangesInput, MockPrepareChangesOutput, Never] = NodeContract(
    input_type=MockPrepareChangesInput, output_type=MockPrepareChangesOutput,
    contract_id=ContractId("engine.write.mock_lifecycle.prepare_changes"), version=ContractVersion("1"),
    reads=(), calls=(SECTION_TARGET,), error_types=(),
    continuation=ContinuationContract(ContractId("engine.write.mock_lifecycle.prepare_changes.state"), ContractVersion("1"), MockPrepareChangesInput),
)

WRITE_CHANGES_CONTRACT: NodeContract[
    MockWriteChangesInput, MockWriteChangesOutput, SnapshotPublicNodeError | SnapshotOperationCancelledNodeError,
] = NodeContract(
    input_type=MockWriteChangesInput, output_type=MockWriteChangesOutput,
    contract_id=ContractId("engine.write.mock_lifecycle.write_changes"), version=ContractVersion("1"),
    reads=(), calls=(PREPARE_TARGET, ASSEMBLE_TARGET, APPLY_TARGET),
    error_types=(SnapshotPublicNodeError, SnapshotOperationCancelledNodeError),
    continuation=ContinuationContract(ContractId("engine.write.mock_lifecycle.write_changes.state"), ContractVersion("1"), MockWriteChangesState),
)


def register_mock_write_orchestrators(registry: NodeRegistry) -> None:
    registry.register_resumable(PrepareChangesNode, PythonNodeExecutor, PREPARE_CHANGES_CONTRACT)
    registry.register_resumable(WriteChangesNode, PythonNodeExecutor, WRITE_CHANGES_CONTRACT)
