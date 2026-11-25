"""One public Time settings batch preparation."""

from dataclasses import dataclass, field
from typing import Never

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.batchPipelineOpenPipeline import TimeSettingsBatchPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsWorkflowContracts import PrepareTimeSettingsBatchInput, PrepareTimeSettingsBatchOutput


@dataclass(frozen=True, kw_only=True)
class PrepareTimeSettingsBatchNode(PythonNode[PrepareTimeSettingsBatchInput, PrepareTimeSettingsBatchOutput, Never]):
    id: NodeId = NodeId("prepare_time_settings_batch")
    skip_on_replan: bool = False
    pipeline: TimeSettingsBatchPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareTimeSettingsBatchInput:
        raise RuntimeError("prepare_time_settings_batch requires explicit invocation input")

    async def execute(self, input: PrepareTimeSettingsBatchInput) -> PrepareTimeSettingsBatchOutput:
        return PrepareTimeSettingsBatchOutput(value=self.pipeline.prepare_batch(input.request))
