"""prepare_epoch_update: one Time public operation."""

from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.epochPipelineOpenPipeline import WorldEpochSettingsPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    PrepareEpochUpdateInput, PrepareEpochUpdateOutput, TimeSettingsNodeError,
)


@dataclass(frozen=True, kw_only=True)
class PrepareEpochUpdateNode(PythonNode[PrepareEpochUpdateInput, PrepareEpochUpdateOutput, TimeSettingsNodeError]):
    id: NodeId = NodeId("prepare_epoch_update")
    skip_on_replan: bool = False
    pipeline: WorldEpochSettingsPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareEpochUpdateInput:
        raise RuntimeError("prepare_epoch_update requires explicit invocation input")

    async def execute(self, input: PrepareEpochUpdateInput) -> PrepareEpochUpdateOutput:
        return PrepareEpochUpdateOutput(value=self.pipeline.prepare_epoch_update(input.request))
