"""One public Time settings section preparation."""

from dataclasses import dataclass, field
from typing import Never

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.worldData.timeSettings.preparation.sectionPipelineOpenPipeline import TimeSettingsSectionPipelineOpenPipeline
from app.dataModel.engine.dag.identity import NodeId
from app.dataModel.engine.nodes.timeSettingsWorkflowContracts import PrepareTimeSettingsSectionInput, PrepareTimeSettingsSectionOutput


@dataclass(frozen=True, kw_only=True)
class PrepareTimeSettingsSectionNode(PythonNode[PrepareTimeSettingsSectionInput, PrepareTimeSettingsSectionOutput, Never]):
    id: NodeId = NodeId("prepare_time_settings_section")
    skip_on_replan: bool = False
    pipeline: TimeSettingsSectionPipelineOpenPipeline = field(repr=False, compare=False)

    async def prepare_input(self, view: DAGReadView) -> PrepareTimeSettingsSectionInput:
        raise RuntimeError("prepare_time_settings_section requires explicit invocation input")

    async def execute(self, input: PrepareTimeSettingsSectionInput) -> PrepareTimeSettingsSectionOutput:
        return PrepareTimeSettingsSectionOutput(value=self.pipeline.prepare_section(input.request))
