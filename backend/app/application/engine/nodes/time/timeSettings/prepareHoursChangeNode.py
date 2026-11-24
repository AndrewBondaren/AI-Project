"""prepare_hours_change: one Time public operation."""

from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.hoursPipelineOpenPipeline import WorldHoursSettingsPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    PrepareHoursChangeInput, PrepareHoursChangeOutput, TimeSettingsNodeError,
)


@dataclass(frozen=True, kw_only=True)
class PrepareHoursChangeNode(PythonNode[PrepareHoursChangeInput, PrepareHoursChangeOutput, TimeSettingsNodeError]):
    id: NodeId = NodeId("prepare_hours_change")
    skip_on_replan: bool = False
    pipeline: WorldHoursSettingsPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareHoursChangeInput:
        raise RuntimeError("prepare_hours_change requires explicit invocation input")

    async def execute(self, input: PrepareHoursChangeInput) -> PrepareHoursChangeOutput:
        return PrepareHoursChangeOutput(value=self.pipeline.prepare_hours_change(input.request))
