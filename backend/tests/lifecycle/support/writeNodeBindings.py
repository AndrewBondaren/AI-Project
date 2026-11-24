"""Explicit test-only registration for the mock Snapshot leaf."""
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.dataModel.engine.dag.identity import ContractId, ContractVersion
from tests.lifecycle.support.assemblePatchSetNode import AssemblePatchSetNode
from tests.lifecycle.support.applySnapshotNode import ApplySnapshotNode
from tests.lifecycle.support.writeNodeContracts import (
    MockAssemblePatchSetInput, MockAssemblePatchSetOutput,
    MockApplySnapshotInput, MockApplySnapshotOutput,
    SnapshotOperationCancelledNodeError, SnapshotPublicNodeError,
)
from typing import Never


ASSEMBLE_PATCH_SET_CONTRACT: NodeContract[
    MockAssemblePatchSetInput, MockAssemblePatchSetOutput, Never,
] = NodeContract(
    MockAssemblePatchSetInput, MockAssemblePatchSetOutput,
    ContractId("engine.patch.mock_lifecycle.assemble_patch_set"), ContractVersion("1"), (),
    error_types=(),
)


APPLY_SNAPSHOT_CONTRACT: NodeContract[
    MockApplySnapshotInput, MockApplySnapshotOutput,
    SnapshotPublicNodeError | SnapshotOperationCancelledNodeError,
] = NodeContract(
    MockApplySnapshotInput, MockApplySnapshotOutput,
    ContractId("engine.snapshot.mock_lifecycle.apply_snapshot"), ContractVersion("1"), (),
    error_types=(SnapshotPublicNodeError, SnapshotOperationCancelledNodeError),
)


def register_mock_apply_snapshot(registry: NodeRegistry) -> None:
    registry.register_python(ApplySnapshotNode, PythonNodeExecutor, APPLY_SNAPSHOT_CONTRACT)


def register_mock_write_leaves(registry: NodeRegistry) -> None:
    registry.register_python(AssemblePatchSetNode, PythonNodeExecutor, ASSEMBLE_PATCH_SET_CONTRACT)
    register_mock_apply_snapshot(registry)
