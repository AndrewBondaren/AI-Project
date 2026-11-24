"""One public PatchSet assembly call for the mock Lifecycle binding."""
from dataclasses import dataclass, field
from typing import Never

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.patch.contracts.assembly import IPatchSetAssembly
from app.dataModel.engine.dag.identity import NodeId
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput, MockPatchSet
from tests.lifecycle.support.writeNodeContracts import MockAssemblePatchSetInput, MockAssemblePatchSetOutput


@dataclass(frozen=True, kw_only=True)
class AssemblePatchSetNode(PythonNode[MockAssemblePatchSetInput, MockAssemblePatchSetOutput, Never]):
    id: NodeId = NodeId("engine.patch.mock_lifecycle.assemble_patch_set")
    skip_on_replan: bool = False
    assembler: IPatchSetAssembly[MockAssemblyInput, MockPatchSet] = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> MockAssemblePatchSetInput:
        raise RuntimeError("assemble_patch_set requires explicit invocation input")

    async def execute(self, input: MockAssemblePatchSetInput) -> MockAssemblePatchSetOutput:
        return MockAssemblePatchSetOutput(value=self.assembler.assemble(input.request))
