"""Mock Lifecycle AB section orchestration through engine CALL."""

import asyncio
from dataclasses import dataclass
from typing import Never

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.invocation.callTarget import CallTarget
from app.application.engine.contracts.invocation.nodeStep import Call, Complete, NodeStep
from app.application.engine.contracts.invocation.resumeEvent import CallCancelled, CallResults, CallRuntimeFailure, CallSuccess, ResumeEvent
from app.application.engine.nodeTypes.resumablePythonNode import ResumablePythonNode
from app.dataModel.engine.dag.identity import CallKey, ContractId, ContractVersion, NodeId
from app.dataModel.lifecycle.results.errors import LifecycleSectionRefused
from tests.lifecycle.support.mixedContracts import LifecycleSectionAB
from tests.lifecycle.support.nodeContracts import SectionNodeInputAB, SectionNodeOutputAB
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput
from tests.lifecycle.support.writeChangesContracts import MockPrepareChangesInput, MockPrepareChangesOutput

SECTION_KEY = CallKey("section_ab")
SECTION_TARGET = CallTarget[SectionNodeInputAB, SectionNodeOutputAB, Never](
    NodeId("engine.lifecycle.prepare_section"), ContractId("engine.lifecycle.prepare_section"),
    ContractVersion("1"), SectionNodeInputAB, SectionNodeOutputAB, (),
)


@dataclass(frozen=True, kw_only=True)
class PrepareChangesNode(ResumablePythonNode[MockPrepareChangesInput, MockPrepareChangesOutput, Never, MockPrepareChangesInput]):
    id: NodeId = NodeId("engine.write.mock_lifecycle.prepare_changes")
    skip_on_replan: bool = False

    async def prepare_input(self, view: DAGReadView) -> MockPrepareChangesInput:
        raise RuntimeError("prepare_changes requires explicit invocation input")

    async def start(self, input: MockPrepareChangesInput) -> NodeStep[MockPrepareChangesOutput, MockPrepareChangesInput]:
        return Call(SECTION_KEY, SECTION_TARGET, SectionNodeInputAB(request=input.section_request), input)

    async def resume(self, state: MockPrepareChangesInput, event: ResumeEvent) -> NodeStep[MockPrepareChangesOutput, MockPrepareChangesInput]:
        if not isinstance(event, CallResults):
            raise TypeError("section CALL result required")
        result = event.get(SECTION_KEY, SECTION_TARGET)
        if isinstance(result, CallSuccess):
            value = result.output.value
            if isinstance(value, LifecycleSectionRefused):
                return Complete(MockPrepareChangesOutput(value=value))
            if not isinstance(value, LifecycleSectionAB):
                raise TypeError("unexpected section result")
            context = state.assembly_context
            request = MockAssemblyInput(
                format_version=context.format_version, operation_id=context.operation_id,
                preparation_fingerprint=context.preparation_fingerprint, world_uid=context.world_uid,
                timeline_id=context.timeline_id, turn_id=context.turn_id,
                expected_world=context.expected_world, expected_players=context.expected_players,
                sections=(state.subject_section, value),
            )
            return Complete(MockPrepareChangesOutput(value=request))
        if isinstance(result, CallCancelled):
            raise asyncio.CancelledError
        if isinstance(result, CallRuntimeFailure):
            raise RuntimeError("section CALL failed")
        raise TypeError("unexpected section CALL result")
