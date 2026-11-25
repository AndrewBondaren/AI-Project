"""Mock write chain: prepare, assemble, apply through engine CALL."""

import asyncio
from dataclasses import dataclass
from typing import Never

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.invocation.callTarget import CallTarget
from app.application.engine.contracts.invocation.nodeStep import Call, Complete, NodeStep
from app.application.engine.contracts.invocation.resumeEvent import CallCancelled, CallFailure, CallResults, CallRuntimeFailure, CallSuccess, ResumeEvent
from app.application.engine.nodeTypes.resumablePythonNode import ResumablePythonNode
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.identity import CallKey, ContractId, ContractVersion, NodeId
from app.dataModel.lifecycle.results.errors import LifecycleSectionRefused
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput, MockPatchSet, MockSnapshotApplyResult
from tests.lifecycle.support.writeChangesContracts import MockPrepareChangesInput, MockPrepareChangesOutput, MockWriteChangesInput, MockWriteChangesOutput, MockWriteChangesState
from tests.lifecycle.support.writeNodeContracts import MockApplySnapshotInput, MockApplySnapshotOutput, MockAssemblePatchSetInput, MockAssemblePatchSetOutput, SnapshotOperationCancelledNodeError, SnapshotPublicNodeError

PREPARE_KEY = CallKey("prepare_changes")
ASSEMBLE_KEY = CallKey("assemble_patch_set")
APPLY_KEY = CallKey("apply_snapshot")
PREPARE_TARGET = CallTarget[MockPrepareChangesInput, MockPrepareChangesOutput, Never](
    NodeId("engine.write.mock_lifecycle.prepare_changes"), ContractId("engine.write.mock_lifecycle.prepare_changes"),
    ContractVersion("1"), MockPrepareChangesInput, MockPrepareChangesOutput, (),
)
ASSEMBLE_TARGET = CallTarget[MockAssemblePatchSetInput, MockAssemblePatchSetOutput, Never](
    NodeId("engine.patch.mock_lifecycle.assemble_patch_set"), ContractId("engine.patch.mock_lifecycle.assemble_patch_set"),
    ContractVersion("1"), MockAssemblePatchSetInput, MockAssemblePatchSetOutput, (),
)
APPLY_TARGET = CallTarget[MockApplySnapshotInput, MockApplySnapshotOutput, SnapshotPublicNodeError | SnapshotOperationCancelledNodeError](
    NodeId("engine.snapshot.mock_lifecycle.apply_snapshot"), ContractId("engine.snapshot.mock_lifecycle.apply_snapshot"),
    ContractVersion("1"), MockApplySnapshotInput, MockApplySnapshotOutput,
    (SnapshotPublicNodeError, SnapshotOperationCancelledNodeError),
)


@dataclass(frozen=True, kw_only=True)
class WriteChangesNode(ResumablePythonNode[
    MockWriteChangesInput, MockWriteChangesOutput,
    SnapshotPublicNodeError | SnapshotOperationCancelledNodeError, MockWriteChangesState,
]):
    id: NodeId = NodeId("engine.write.mock_lifecycle.write_changes")
    skip_on_replan: bool = False

    async def prepare_input(self, view: DAGReadView) -> MockWriteChangesInput:
        raise RuntimeError("write_changes requires explicit invocation input")

    async def start(self, input: MockWriteChangesInput) -> NodeStep[MockWriteChangesOutput, MockWriteChangesState]:
        return Call(PREPARE_KEY, PREPARE_TARGET, input.preparation,
                    MockWriteChangesState(stage="prepare", request=input))

    async def resume(self, state: MockWriteChangesState, event: ResumeEvent) -> NodeStep[MockWriteChangesOutput, MockWriteChangesState]:
        if not isinstance(event, CallResults):
            raise TypeError("write CALL result required")
        if state.stage == "prepare":
            result = event.get(PREPARE_KEY, PREPARE_TARGET)
            if isinstance(result, CallSuccess):
                value = result.output.value
                if isinstance(value, LifecycleSectionRefused):
                    return Complete(MockWriteChangesOutput(value=value))
                if not isinstance(value, MockAssemblyInput):
                    raise TypeError("unexpected preparation result")
                return Call(ASSEMBLE_KEY, ASSEMBLE_TARGET, MockAssemblePatchSetInput(request=value),
                            MockWriteChangesState(stage="assemble", request=state.request))
        elif state.stage == "assemble":
            result = event.get(ASSEMBLE_KEY, ASSEMBLE_TARGET)
            if isinstance(result, CallSuccess):
                value = result.output.value
                if isinstance(value, PatchSetAssemblyRefused):
                    return Complete(MockWriteChangesOutput(value=value))
                if not isinstance(value, MockPatchSet):
                    raise TypeError("unexpected assembly result")
                return Call(APPLY_KEY, APPLY_TARGET, MockApplySnapshotInput(patch_set=value),
                            MockWriteChangesState(stage="apply", request=state.request))
        elif state.stage == "apply":
            result = event.get(APPLY_KEY, APPLY_TARGET)
            if isinstance(result, CallSuccess):
                value = result.output.value
                if not isinstance(value, MockSnapshotApplyResult):
                    raise TypeError("unexpected apply result")
                return Complete(MockWriteChangesOutput(value=value))
        else:
            raise TypeError("unknown write stage")
        if isinstance(result, CallFailure):
            raise PythonNodeError(result.error)
        if isinstance(result, CallCancelled):
            raise asyncio.CancelledError
        if isinstance(result, CallRuntimeFailure):
            raise RuntimeError("write child CALL failed")
        raise TypeError("unexpected write CALL result")
