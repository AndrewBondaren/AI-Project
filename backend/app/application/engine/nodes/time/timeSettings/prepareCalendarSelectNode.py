"""prepare_calendar_select: one Time public operation."""

from dataclasses import dataclass, field

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.calendarPipelineOpenPipeline import WorldCalendarSettingsPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsContracts import (
    PrepareCalendarSelectInput, PrepareCalendarSelectOutput, TimeSettingsNodeError,
)


@dataclass(frozen=True, kw_only=True)
class PrepareCalendarSelectNode(PythonNode[PrepareCalendarSelectInput, PrepareCalendarSelectOutput, TimeSettingsNodeError]):
    id: NodeId = NodeId("prepare_calendar_select")
    skip_on_replan: bool = False
    pipeline: WorldCalendarSettingsPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareCalendarSelectInput:
        raise RuntimeError("prepare_calendar_select requires explicit invocation input")

    async def execute(self, input: PrepareCalendarSelectInput) -> PrepareCalendarSelectOutput:
        return PrepareCalendarSelectOutput(value=self.pipeline.prepare_calendar_select(input.request))
