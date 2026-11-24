"""prepare_calendar_update: one Time public operation."""

from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.calendarPipelineOpenPipeline import WorldCalendarSettingsPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    PrepareCalendarUpdateInput, PrepareCalendarUpdateOutput, TimeSettingsNodeError,
)


@dataclass(frozen=True, kw_only=True)
class PrepareCalendarUpdateNode(PythonNode[PrepareCalendarUpdateInput, PrepareCalendarUpdateOutput, TimeSettingsNodeError]):
    id: NodeId = NodeId("prepare_calendar_update")
    skip_on_replan: bool = False
    pipeline: WorldCalendarSettingsPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareCalendarUpdateInput:
        raise RuntimeError("prepare_calendar_update requires explicit invocation input")

    async def execute(self, input: PrepareCalendarUpdateInput) -> PrepareCalendarUpdateOutput:
        return PrepareCalendarUpdateOutput(value=self.pipeline.prepare_calendar_update(input.request))
