"""One public Snapshot apply call for the mock Lifecycle binding."""
from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.worldSnapshot.contracts.applyPort import IWorldSnapshotApply
from app.application.worldSnapshot.errors import SnapshotOperationCancelledError, SnapshotPublicError
from app.dataModel.engine.dag.identity import NodeId
from tests.lifecycle.support.snapshotContracts import MockSectionUnion, MockSnapshotApplyResult
from tests.lifecycle.support.writeNodeContracts import (
    MockApplySnapshotInput, MockApplySnapshotOutput,
    SnapshotOperationCancelledNodeError, SnapshotPublicNodeError,
)


@dataclass(frozen=True, kw_only=True)
class ApplySnapshotNode(PythonNode[MockApplySnapshotInput, MockApplySnapshotOutput,
                                   SnapshotPublicNodeError | SnapshotOperationCancelledNodeError]):
    id: NodeId = NodeId("engine.snapshot.mock_lifecycle.apply_snapshot")
    skip_on_replan: bool = False
    snapshot: IWorldSnapshotApply[MockSectionUnion, MockSnapshotApplyResult] = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> MockApplySnapshotInput:
        raise RuntimeError("apply_snapshot requires explicit invocation input")

    async def execute(self, input: MockApplySnapshotInput) -> MockApplySnapshotOutput:
        try:
            result = await self.snapshot.apply(input.patch_set)
        except SnapshotPublicError as exc:
            raise PythonNodeError(SnapshotPublicNodeError(fault=exc.fault)) from exc
        except SnapshotOperationCancelledError as exc:
            raise PythonNodeError(SnapshotOperationCancelledNodeError(outcome=exc.outcome)) from exc
        return MockApplySnapshotOutput(value=result)
