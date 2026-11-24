"""prepare_epoch_remove: one Time public operation."""

from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.epochPipelineOpenPipeline import WorldEpochSettingsPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    PrepareEpochRemoveInput, PrepareEpochRemoveOutput, TimeSettingsNodeError,
)


@dataclass(frozen=True, kw_only=True)
class PrepareEpochRemoveNode(PythonNode[PrepareEpochRemoveInput, PrepareEpochRemoveOutput, TimeSettingsNodeError]):
    id: NodeId = NodeId("prepare_epoch_remove")
    skip_on_replan: bool = False
    pipeline: WorldEpochSettingsPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareEpochRemoveInput:
        raise RuntimeError("prepare_epoch_remove requires explicit invocation input")

    async def execute(self, input: PrepareEpochRemoveInput) -> PrepareEpochRemoveOutput:
        return PrepareEpochRemoveOutput(value=self.pipeline.prepare_epoch_remove(input.request))
