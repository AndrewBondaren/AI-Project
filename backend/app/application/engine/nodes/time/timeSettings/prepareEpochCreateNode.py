"""prepare_epoch_create: one Time public operation."""

from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.epochPipelineOpenPipeline import WorldEpochSettingsPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    PrepareEpochCreateInput, PrepareEpochCreateOutput, TimeSettingsNodeError,
)


@dataclass(frozen=True, kw_only=True)
class PrepareEpochCreateNode(PythonNode[PrepareEpochCreateInput, PrepareEpochCreateOutput, TimeSettingsNodeError]):
    id: NodeId = NodeId("prepare_epoch_create")
    skip_on_replan: bool = False
    pipeline: WorldEpochSettingsPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareEpochCreateInput:
        raise RuntimeError("prepare_epoch_create requires explicit invocation input")

    async def execute(self, input: PrepareEpochCreateInput) -> PrepareEpochCreateOutput:
        return PrepareEpochCreateOutput(value=self.pipeline.prepare_epoch_create(input.request))
