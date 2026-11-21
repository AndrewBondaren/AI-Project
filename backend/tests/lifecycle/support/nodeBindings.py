"""Nine explicit mock registrations; injected ready inputs and public pipelines."""
from dataclasses import dataclass
from typing import Never
from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.dataModel.engine.dag.identity import NodeId
from tests.lifecycle.support import mixedContracts as m
from tests.lifecycle.support import nodeContracts as c
from app.application.lifecycle.changes.createPipelineOpenPipeline import ILifecycleCreatePipelineOpenPipeline
from app.application.lifecycle.changes.replacementPipelineOpenPipeline import ILifecycleReplacementPipelineOpenPipeline
from app.application.lifecycle.changes.endPipelineOpenPipeline import ILifecycleEndPipelineOpenPipeline
from app.application.lifecycle.changes.reactivatePipelineOpenPipeline import ILifecycleReactivatePipelineOpenPipeline
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import ILifecycleSectionPipelineOpenPipeline


@dataclass(frozen=True, kw_only=True)
class CreateANode(PythonNode[c.CreateNodeInputA, c.CreateNodeOutputA, Never]):
    id: NodeId = NodeId("engine.lifecycle.test_a.prepare_create")
    ready_input: c.CreateNodeInputA
    pipeline: ILifecycleCreatePipelineOpenPipeline[m.CreateRequestA, m.CreateA]

    async def prepare_input(self, view: DAGReadView) -> c.CreateNodeInputA:
        return self.ready_input

    async def execute(self, input: c.CreateNodeInputA) -> c.CreateNodeOutputA:
        if type(input) is not c.CreateNodeInputA:
            raise TypeError("wrong concrete node input")
        admitted = c.CreateNodeInputA.model_validate(input, strict=True)
        return c.CreateNodeOutputA(value=self.pipeline.prepare_create(admitted.request))


@dataclass(frozen=True, kw_only=True)
class CreateBNode(PythonNode[c.CreateNodeInputB, c.CreateNodeOutputB, Never]):
    id: NodeId = NodeId("engine.lifecycle.test_b.prepare_create")
    ready_input: c.CreateNodeInputB
    pipeline: ILifecycleCreatePipelineOpenPipeline[m.CreateRequestB, m.CreateB]

    async def prepare_input(self, view: DAGReadView) -> c.CreateNodeInputB:
        return self.ready_input

    async def execute(self, input: c.CreateNodeInputB) -> c.CreateNodeOutputB:
        if type(input) is not c.CreateNodeInputB:
            raise TypeError("wrong concrete node input")
        admitted = c.CreateNodeInputB.model_validate(input, strict=True)
        return c.CreateNodeOutputB(value=self.pipeline.prepare_create(admitted.request))


@dataclass(frozen=True, kw_only=True)
class ReplaceANode(PythonNode[c.ReplaceNodeInputA, c.ReplaceNodeOutputA, Never]):
    id: NodeId = NodeId("engine.lifecycle.test_a.prepare_replacement")
    ready_input: c.ReplaceNodeInputA
    pipeline: ILifecycleReplacementPipelineOpenPipeline[m.ReplaceRequestA, m.ReplaceA]

    async def prepare_input(self, view: DAGReadView) -> c.ReplaceNodeInputA:
        return self.ready_input

    async def execute(self, input: c.ReplaceNodeInputA) -> c.ReplaceNodeOutputA:
        if type(input) is not c.ReplaceNodeInputA:
            raise TypeError("wrong concrete node input")
        admitted = c.ReplaceNodeInputA.model_validate(input, strict=True)
        return c.ReplaceNodeOutputA(value=self.pipeline.prepare_replacement(admitted.request))


@dataclass(frozen=True, kw_only=True)
class ReplaceBNode(PythonNode[c.ReplaceNodeInputB, c.ReplaceNodeOutputB, Never]):
    id: NodeId = NodeId("engine.lifecycle.test_b.prepare_replacement")
    ready_input: c.ReplaceNodeInputB
    pipeline: ILifecycleReplacementPipelineOpenPipeline[m.ReplaceRequestB, m.ReplaceB]

    async def prepare_input(self, view: DAGReadView) -> c.ReplaceNodeInputB:
        return self.ready_input

    async def execute(self, input: c.ReplaceNodeInputB) -> c.ReplaceNodeOutputB:
        if type(input) is not c.ReplaceNodeInputB:
            raise TypeError("wrong concrete node input")
        admitted = c.ReplaceNodeInputB.model_validate(input, strict=True)
        return c.ReplaceNodeOutputB(value=self.pipeline.prepare_replacement(admitted.request))


@dataclass(frozen=True, kw_only=True)
class EndANode(PythonNode[c.EndNodeInputA, c.EndNodeOutputA, Never]):
    id: NodeId = NodeId("engine.lifecycle.test_a.prepare_end")
    ready_input: c.EndNodeInputA
    pipeline: ILifecycleEndPipelineOpenPipeline[m.EndRequestA, m.EndA]

    async def prepare_input(self, view: DAGReadView) -> c.EndNodeInputA:
        return self.ready_input

    async def execute(self, input: c.EndNodeInputA) -> c.EndNodeOutputA:
        if type(input) is not c.EndNodeInputA:
            raise TypeError("wrong concrete node input")
        admitted = c.EndNodeInputA.model_validate(input, strict=True)
        return c.EndNodeOutputA(value=self.pipeline.prepare_end(admitted.request))


@dataclass(frozen=True, kw_only=True)
class EndBNode(PythonNode[c.EndNodeInputB, c.EndNodeOutputB, Never]):
    id: NodeId = NodeId("engine.lifecycle.test_b.prepare_end")
    ready_input: c.EndNodeInputB
    pipeline: ILifecycleEndPipelineOpenPipeline[m.EndRequestB, m.EndB]

    async def prepare_input(self, view: DAGReadView) -> c.EndNodeInputB:
        return self.ready_input

    async def execute(self, input: c.EndNodeInputB) -> c.EndNodeOutputB:
        if type(input) is not c.EndNodeInputB:
            raise TypeError("wrong concrete node input")
        admitted = c.EndNodeInputB.model_validate(input, strict=True)
        return c.EndNodeOutputB(value=self.pipeline.prepare_end(admitted.request))


@dataclass(frozen=True, kw_only=True)
class ReactivateANode(PythonNode[c.ReactivateNodeInputA, c.ReactivateNodeOutputA, Never]):
    id: NodeId = NodeId("engine.lifecycle.test_a.prepare_reactivate")
    ready_input: c.ReactivateNodeInputA
    pipeline: ILifecycleReactivatePipelineOpenPipeline[m.ReactivateRequestA, m.ReactivateA]

    async def prepare_input(self, view: DAGReadView) -> c.ReactivateNodeInputA:
        return self.ready_input

    async def execute(self, input: c.ReactivateNodeInputA) -> c.ReactivateNodeOutputA:
        if type(input) is not c.ReactivateNodeInputA:
            raise TypeError("wrong concrete node input")
        admitted = c.ReactivateNodeInputA.model_validate(input, strict=True)
        return c.ReactivateNodeOutputA(value=self.pipeline.prepare_reactivate(admitted.request))


@dataclass(frozen=True, kw_only=True)
class ReactivateBNode(PythonNode[c.ReactivateNodeInputB, c.ReactivateNodeOutputB, Never]):
    id: NodeId = NodeId("engine.lifecycle.test_b.prepare_reactivate")
    ready_input: c.ReactivateNodeInputB
    pipeline: ILifecycleReactivatePipelineOpenPipeline[m.ReactivateRequestB, m.ReactivateB]

    async def prepare_input(self, view: DAGReadView) -> c.ReactivateNodeInputB:
        return self.ready_input

    async def execute(self, input: c.ReactivateNodeInputB) -> c.ReactivateNodeOutputB:
        if type(input) is not c.ReactivateNodeInputB:
            raise TypeError("wrong concrete node input")
        admitted = c.ReactivateNodeInputB.model_validate(input, strict=True)
        return c.ReactivateNodeOutputB(value=self.pipeline.prepare_reactivate(admitted.request))


@dataclass(frozen=True, kw_only=True)
class SectionABNode(PythonNode[c.SectionNodeInputAB, c.SectionNodeOutputAB, Never]):
    id: NodeId = NodeId("engine.lifecycle.prepare_section")
    ready_input: c.SectionNodeInputAB
    pipeline: ILifecycleSectionPipelineOpenPipeline[m.PrepareLifecycleSectionAB, m.LifecycleSectionAB]

    async def prepare_input(self, view: DAGReadView) -> c.SectionNodeInputAB:
        return self.ready_input

    async def execute(self, input: c.SectionNodeInputAB) -> c.SectionNodeOutputAB:
        if type(input) is not c.SectionNodeInputAB:
            raise TypeError("wrong concrete node input")
        admitted = c.SectionNodeInputAB.model_validate(input, strict=True)
        return c.SectionNodeOutputAB(value=self.pipeline.prepare_section(admitted.request))


def register_mock_nodes(registry: NodeRegistry) -> None:
    registry.register_python(CreateANode, PythonNodeExecutor, c.CREATEA_CONTRACT)
    registry.register_python(CreateBNode, PythonNodeExecutor, c.CREATEB_CONTRACT)
    registry.register_python(ReplaceANode, PythonNodeExecutor, c.REPLACEA_CONTRACT)
    registry.register_python(ReplaceBNode, PythonNodeExecutor, c.REPLACEB_CONTRACT)
    registry.register_python(EndANode, PythonNodeExecutor, c.ENDA_CONTRACT)
    registry.register_python(EndBNode, PythonNodeExecutor, c.ENDB_CONTRACT)
    registry.register_python(ReactivateANode, PythonNodeExecutor, c.REACTIVATEA_CONTRACT)
    registry.register_python(ReactivateBNode, PythonNodeExecutor, c.REACTIVATEB_CONTRACT)
    registry.register_python(SectionABNode, PythonNodeExecutor, c.SECTIONAB_CONTRACT)

