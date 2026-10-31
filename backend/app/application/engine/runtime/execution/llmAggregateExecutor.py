"""One initial LLM call and local typed outcomes; coordinator alone publishes."""

import asyncio
from collections.abc import Callable, Mapping
import json
import sys
from time import time
from typing import cast

from pydantic import BaseModel

from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan, LLMGroup
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.nodeOutcome import NodeOutcome
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.application.engine.runtime.prompt.pojo.nodeSection import NodeSection
from app.application.engine.runtime.repair.dslFailureProjector import DSLFailureProjector
from app.application.engine.runtime.repair.pojo.nodeFailureContext import NodeFailureContext
from app.application.engine.runtime.repair.repairOrchestrator import GroupValidation, RepairOrchestrator, cancellation_checkpoint
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.llmValidator import LLMValidator
from app.application.engine.validation.nodeValidationError import NodeErrorSeverity, NodeValidationError
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.llm.models import ChatMessage
from app.dataModel.engine.dag.diagnostics import (
    CancellationReason, CancellationSource, ExecutionDiagnostic, ExecutionEventCode, ExecutionSeverity,
)
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import ExecutionIdentity, NodeId
from app.dataModel.engine.dag.nodeStatus import NodeStatus


class LLMAggregateExecutor:
    def __init__(
        self, builder: LLMGroupPayloadBuilder, validator: LLMValidator,
        projector: DSLFailureProjector, repair: RepairOrchestrator, *, clock: Callable[[], float] = time,
    ) -> None:
        self._builder, self._validator = builder, validator
        self._projector, self._repair, self._clock = projector, repair, clock

    @staticmethod
    def node(plan: ExecutionPlan, node_id: NodeId) -> LLMNode[BaseModel, BaseModel, NodeError]:
        registration = plan.registrations[node_id]
        node = plan.get(node_id, registration.contract).node
        if not isinstance(node, LLMNode):
            raise TypeError("LLM group requires LLMNode")
        return node

    async def execute(
        self, plan: ExecutionPlan, group: LLMGroup, identities: tuple[ExecutionIdentity, ...],
        views: Mapping[NodeId, PublishedDAGReadView], request: LLMRequest, *,
        options: LLMExecutionOptions, pass_number: int = 0, level: int = 0,
    ) -> tuple[NodeOutcome[BaseModel, NodeError], ...]:
        started = self._clock()
        sections: list[NodeSection[BaseModel]] = []
        nodes = tuple(node for row in group.levels for node in row)
        if tuple(identity.node_id for identity in identities) != nodes:
            raise ValueError("LLM identities do not match ordered group")
        preparing = True
        active: ExecutionIdentity | None = None
        try:
            options.__post_init__()
            for identity in identities:
                active = identity
                cancellation_checkpoint()
                node = self.node(plan, identity.node_id)
                view = views[identity.node_id]
                if view.consumer != identity.node_id or view.execution_id != identity.execution_id:
                    raise ValueError("LLM view and identity do not match")
                input_value = await node.prepare_input(view)
                cancellation_checkpoint()
                sections.append(self._builder.section(node, plan.registrations[identity.node_id], input_value, language=options.language))
            preparing = False
            base = self._builder.build(tuple(sections), player_message=options.player_message, language=options.language)
            messages: list[ChatMessage] = []
            if options.system_role:
                messages.append(ChatMessage(role="system", content=base.global_dsl))
            wire = base.to_user_dict() if options.system_role else base.to_dict()
            messages.append(ChatMessage(role="user", content=json.dumps(wire, ensure_ascii=False)))
            enable_thinking = any(self.node(plan, node).enable_thinking for node in nodes)
            transport: dict[NodeId, object] = {}
            keys: dict[NodeId, tuple[str, ...]] = {}
            pending = nodes

            def validate(raw: str, attempt: int) -> GroupValidation:
                nonlocal pending
                envelope_error: ValidationResult | None = None
                try:
                    parsed: object = json.loads(raw)
                    if not isinstance(parsed, dict):
                        raise ValueError("LLM response must be an object")
                    # JSON transport erasure only; typed Outputs are admitted
                    # separately under each registered owning POJO schema.
                    response = cast(dict[str, object], parsed)
                    if set(response).difference(pending):
                        raise ValueError("LLM response has unexpected sections")
                    for node_id in pending:
                        transport.pop(node_id, None)
                        if node_id in response:
                            transport[node_id] = response[node_id]
                except (ValueError, TypeError):
                    transport.clear()
                    envelope_error = self._invalid("invalid_json", "invalid group response envelope")
                outcomes: list[NodeOutcome[BaseModel, NodeError]] = []
                failures: list[NodeFailureContext[BaseModel]] = []
                for identity in identities:
                    node_id, view = identity.node_id, views[identity.node_id]
                    registration = plan.registrations[node_id]
                    raw_section = json.dumps(transport[node_id], ensure_ascii=False) if node_id in transport else None
                    output: BaseModel | None = None
                    validation = envelope_error
                    if validation is None:
                        if raw_section is None:
                            validation = self._invalid("missing_section", "missing group response section")
                        else:
                            output, validation = self._validator.validate(raw_section, registration.contract, identity,
                                                                          pass_number=pass_number, repair_attempt=attempt)
                    cancellation_checkpoint()
                    status = NodeStatus.SUCCESS if output is not None and validation.ok else NodeStatus.FAILED
                    outcomes.append(self.outcome(identity, view, status, started, pass_number, level,
                                                 output=output if status == NodeStatus.SUCCESS else None, validation=validation))
                    if status != NodeStatus.SUCCESS:
                        failure = self._projector.project(
                            self.node(plan, node_id), registration, identity, validation,
                            raw_output=raw if envelope_error is not None else raw_section,
                            dsl_keys=keys.get(node_id), reads=view.dependency_reads, domain_reads=view.domain_reads,
                            pass_number=pass_number, repair_attempt=attempt,
                        )
                        keys[node_id] = failure.dsl_keys
                        failures.append(failure)
                pending = tuple(failure.identity.node_id for failure in failures)
                return tuple(outcomes), tuple(failures)

            raw = await request(messages, base.response_format_schema, enable_thinking=enable_thinking, temperature=group.temperature)
            cancellation_checkpoint()
            messages.append(ChatMessage(role="assistant", content=raw))
            outcomes = await self._repair.repair(base, validate(raw, 0), messages, request, validate,
                                                 options=options, enable_thinking=enable_thinking, temperature=group.temperature)
            cancellation_checkpoint()
            return outcomes
        except asyncio.CancelledError:
            # Deliver a pending task.cancel() suppressed by a provider/prepare
            # callback before returning a local cancellation outcome.
            try:
                await asyncio.sleep(0)
            except asyncio.CancelledError:
                pass
            return tuple(self.outcome(identity, views[identity.node_id], NodeStatus.CANCELLED, started,
                                      pass_number, level, message="LLM group cancelled") for identity in identities)
        except PythonNodeError:
            admitted: NodeError | None = None
            if preparing and active is not None:
                admitted, _ = ContractValidator().validate_error(
                    cast(PythonNodeError[NodeError], sys.exception()).error,
                    plan.registrations[active.node_id].contract.error_types,
                )
            return tuple(self.outcome(identity, views[identity.node_id], NodeStatus.FAILED, started, pass_number, level,
                                      error=admitted if identity == active else None, message="LLM operation error") for identity in identities)
        except Exception as error:
            return tuple(self.outcome(identity, views[identity.node_id], NodeStatus.FAILED, started, pass_number, level,
                                      message=f"LLM group: {type(error).__name__}") for identity in identities)

    @staticmethod
    def _invalid(code: str, message: str) -> ValidationResult:
        return ValidationResult(status=ValidationStatus.RETRY, errors=[
            NodeValidationError(code=code, message=message, severity=NodeErrorSeverity.RETRY),
        ])

    def outcome(
        self, identity: ExecutionIdentity, view: PublishedDAGReadView, status: NodeStatus,
        started: float, pass_number: int, level: int, *, output: BaseModel | None = None,
        validation: ValidationResult | None = None, error: NodeError | None = None, message: str = "LLM group validation",
    ) -> NodeOutcome[BaseModel, NodeError]:
        completed = self._clock()
        cancelled = status == NodeStatus.CANCELLED
        diagnostic = ExecutionDiagnostic(
            identity=identity, pass_number=pass_number, phase=ExecutionPhase.LLM, level=level,
            timestamp=completed, completed_at=completed,
            code=ExecutionEventCode.CANCEL_OBSERVED if cancelled else ExecutionEventCode.NODE_FINISHED,
            severity=ExecutionSeverity.ERROR if status == NodeStatus.FAILED else ExecutionSeverity.INFO,
            status=status, message=message, reads=view.dependency_reads,
            cancel_source=CancellationSource.UNKNOWN if cancelled else None,
            cancel_reason=CancellationReason.UNKNOWN if cancelled else None,
            cancel_observed_at=completed if cancelled else None,
        )
        return NodeOutcome[BaseModel, NodeError](identity=identity, status=status, started_at=started, completed_at=completed,
                                                output=output, error=error, validation=validation,
                                                reads=view.dependency_reads, domain_reads=view.domain_reads, diagnostics=(diagnostic,))
