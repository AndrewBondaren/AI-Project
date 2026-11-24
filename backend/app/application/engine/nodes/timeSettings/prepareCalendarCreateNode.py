"""prepare_calendar_create: one Time public operation."""

from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.calendarPipelineOpenPipeline import WorldCalendarSettingsPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    PrepareCalendarCreateInput, PrepareCalendarCreateOutput, TimeSettingsNodeError,
)


@dataclass(frozen=True, kw_only=True)
class PrepareCalendarCreateNode(PythonNode[PrepareCalendarCreateInput, PrepareCalendarCreateOutput, TimeSettingsNodeError]):
    id: NodeId = NodeId("prepare_calendar_create")
    skip_on_replan: bool = False
    pipeline: WorldCalendarSettingsPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareCalendarCreateInput:
        raise RuntimeError("prepare_calendar_create requires explicit invocation input")

    async def execute(self, input: PrepareCalendarCreateInput) -> PrepareCalendarCreateOutput:
        return PrepareCalendarCreateOutput(value=self.pipeline.prepare_calendar_create(input.request))
