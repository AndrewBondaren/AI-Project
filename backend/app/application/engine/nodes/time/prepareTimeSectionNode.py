"""Prepare a native Time section through its public pipeline."""

from dataclasses import dataclass, field
from typing import Never

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.time.changes.advancePipelineOpenPipeline import ITimeAdvancePipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.time.contracts import PrepareTimeSectionInput, PrepareTimeSectionOutput


@dataclass(frozen=True, kw_only=True)
class PrepareTimeSectionNode(PythonNode[PrepareTimeSectionInput, PrepareTimeSectionOutput, Never]):
    id: NodeId = NodeId("prepare_time_section")
    skip_on_replan: bool = False
    pipeline: ITimeAdvancePipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareTimeSectionInput:
        raise RuntimeError("prepare_time_section requires explicit invocation input")

    async def execute(self, input: PrepareTimeSectionInput) -> PrepareTimeSectionOutput:
        return PrepareTimeSectionOutput(value=self.pipeline.prepare_section(input.request))
