"""prepare_calendar_remove: one Time public operation."""

from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.calendarPipelineOpenPipeline import WorldCalendarSettingsPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    PrepareCalendarRemoveInput, PrepareCalendarRemoveOutput, TimeSettingsNodeError,
)


@dataclass(frozen=True, kw_only=True)
class PrepareCalendarRemoveNode(PythonNode[PrepareCalendarRemoveInput, PrepareCalendarRemoveOutput, TimeSettingsNodeError]):
    id: NodeId = NodeId("prepare_calendar_remove")
    skip_on_replan: bool = False
    pipeline: WorldCalendarSettingsPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareCalendarRemoveInput:
        raise RuntimeError("prepare_calendar_remove requires explicit invocation input")

    async def execute(self, input: PrepareCalendarRemoveInput) -> PrepareCalendarRemoveOutput:
        return PrepareCalendarRemoveOutput(value=self.pipeline.prepare_calendar_remove(input.request))
