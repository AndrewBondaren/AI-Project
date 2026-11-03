"""Local Python pipeline; all shared writes belong to the coordinator."""

import asyncio
import sys
from collections.abc import Callable
from time import time
from typing import cast

from pydantic import BaseModel, TypeAdapter

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.contracts.invocation.nodeStep import Complete
from app.application.engine.contracts.invocation.resumeEvent import ResumeEvent
from app.application.engine.nodeTypes.resumablePythonNode import ResumablePythonNode
from app.application.engine.runtime.invocations.stepEffect import StepEffect
from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.nodeTypes.support.nodeKind import NodeKind
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, NodeOutcome, NodeStage
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.validation.validationStatus import ValidationResult
from app.dataModel.engine.dag.diagnostics import (
    CancellationReason, CancellationSource, ExecutionDiagnostic, ExecutionEventCode,
    ExecutionSeverity, Index,
)
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import ExecutionIdentity
from app.dataModel.engine.dag.nodeStatus import NodeStatus


class NodeRunner:
    def __init__(
        self, structural: ContractValidator, semantic: NodeValidator, *, clock: Callable[[], float] = time,
    ) -> None:
        self._structural = structural
        self._semantic = semantic
        self._clock = clock

    async def run_resumable(
        self, node: ResumablePythonNode[BaseModel, BaseModel, NodeError, BaseModel], view: PublishedDAGReadView,
        identity: ExecutionIdentity, registration: NodeRegistration[BaseModel, BaseModel, NodeError],
        prepared: BaseModel | None, state: BaseModel | None, event: ResumeEvent | None,
        pass_number: int, apply_error_policy: bool,
    ) -> StepEffect:
        contract = registration.contract
        try:
            if state is None:
                raw_input = prepared if prepared is not None else await node.prepare_input(view)
                admitted, validation = self._structural.validate(raw_input, contract.input_type)
                if admitted is None or not validation.ok:
                    raise TypeError("invalid resumable input")
                prepared = admitted
                step = await node.start(admitted)
            elif event is not None:
                step = await node.resume(state, event)
            else:
                raise ValueError("continuation has no resume event")
            if isinstance(step, Complete):
                output, validation = self._structural.validate(step.output, contract.output_type)
                if output is None or not validation.ok:
                    raise TypeError("invalid resumable output")
                if not self._semantic.validate(NodeValidationContext(output, identity, pass_number), contract).ok:
                    raise ValueError("resumable output failed semantic validation")
                step = Complete(output)
            return StepEffect(step=step, prepared=prepared, reads=view.dependency_reads, domain_reads=view.domain_reads)
        except asyncio.CancelledError:
            return StepEffect(cancelled=True, reads=view.dependency_reads, domain_reads=view.domain_reads)
        except Exception as exc:
            failure_type = type(exc).__name__
            if isinstance(exc, PythonNodeError):
                raw_error = cast(PythonNodeError[NodeError], exc).error
                error, validation = self._structural.validate_error(raw_error, contract.error_types)
                if error is not None and validation.ok:
                    policy = contract.error_policy if apply_error_policy else None
                    return StepEffect(error=error, gate=policy(error) if policy else None,
                                      reads=view.dependency_reads, domain_reads=view.domain_reads)
            now = self._clock()
            diagnostic = ExecutionDiagnostic(
                identity=identity, phase=node.phase, pass_number=pass_number, level=0, timestamp=now,
                completed_at=now, status=NodeStatus.FAILED, code=ExecutionEventCode.NODE_FINISHED,
                severity=ExecutionSeverity.ERROR, message=failure_type, reads=view.dependency_reads,
            )
            return StepEffect(diagnostics=(diagnostic,), reads=view.dependency_reads, domain_reads=view.domain_reads)

    async def run[I: BaseModel, O: BaseModel, E: NodeError](
        self, node: PythonNode[I, O, E], view: PublishedDAGReadView, identity: ExecutionIdentity,
        registration: NodeRegistration[I, O, E], executor: PythonExecutor, *, pass_number: Index = 0, level: Index = 0,
        explicit_input: I | None = None, apply_error_policy: bool = True,
        on_prepared: Callable[[I], None] | None = None,
    ) -> NodeOutcome[O, E]:
        ExecutionIdentity.model_validate(identity)
        TypeAdapter[int](Index).validate_python(pass_number)
        TypeAdapter[int](Index).validate_python(level)
        started_at = self._clock()
        stage = NodeStage.ADMISSION
        task = asyncio.current_task()

        def finish(
            status: NodeStatus, message: str, *, output: O | None = None,
            gate: GateSignal | None = None, validation: ValidationResult | None = None,
            cancel_observed_at: float | None = None,
            error: E | None = None,
        ) -> NodeOutcome[O, E]:
            completed_at = self._clock()
            cancelled = status == NodeStatus.CANCELLED
            code = ExecutionEventCode.NODE_FINISHED
            if cancelled:
                code = ExecutionEventCode.CANCEL_OBSERVED
            elif gate is not None:
                code = ExecutionEventCode.REPLAN_REQUESTED
            diagnostic = ExecutionDiagnostic(
                identity=identity, pass_number=pass_number, phase=node.phase, level=level,
                timestamp=completed_at, code=code, status=status,
                severity=ExecutionSeverity.ERROR if status == NodeStatus.FAILED else ExecutionSeverity.INFO,
                message=message, reads=view.dependency_reads, completed_at=completed_at,
                cancel_source=CancellationSource.UNKNOWN if cancelled else None,
                cancel_reason=CancellationReason.UNKNOWN if cancelled else None,
                cancel_observed_at=cancel_observed_at,
            )
            return NodeOutcome[O, E](
                identity=identity, status=status, output=output, gate=gate, validation=validation,
                reads=view.dependency_reads, domain_reads=view.domain_reads,
                started_at=started_at, completed_at=completed_at, diagnostics=(diagnostic,),
                error=error,
            )

        async def cancelled(message: str) -> NodeOutcome[O, E]:
            observed_at = self._clock()
            # A synchronous callback may call task.cancel() before asyncio
            # has injected it. Consume that pending delivery so returning a
            # local CANCELLED outcome does not lose it to Task cancellation.
            try:
                await asyncio.sleep(0)
            except asyncio.CancelledError:
                pass
            return finish(NodeStatus.CANCELLED, message, cancel_observed_at=observed_at)

        try:
            registration.validate_node(node)
            if registration.kind != NodeKind.PYTHON or registration.executor_cls is None:
                raise TypeError("runner requires a Python binding")
            if not isinstance(executor, registration.executor_cls):
                raise TypeError("executor does not match binding")
            if identity.node_id != node.id or view.consumer != node.id or view.execution_id != identity.execution_id:
                raise ValueError("node, attempt and view do not belong together")
            if task is not None and task.cancelling():
                raise asyncio.CancelledError
            stage = NodeStage.PREPARE
            prepared = explicit_input if explicit_input is not None else await node.prepare_input(view)
            if task is not None and task.cancelling():
                raise asyncio.CancelledError
            stage = NodeStage.INPUT_VALIDATION
            input, validation = self._structural.validate(prepared, registration.contract.input_type)
            if input is None or not validation.ok:
                return finish(NodeStatus.FAILED, stage.value, validation=validation)
            if on_prepared is not None:
                on_prepared(input)
            stage = NodeStage.EXECUTE
            produced = await executor.execute(node, input)
            if task is not None and task.cancelling():
                raise asyncio.CancelledError
            stage = NodeStage.OUTPUT_VALIDATION
            output, validation = self._structural.validate(produced, registration.contract.output_type)
            if output is None or not validation.ok:
                return finish(NodeStatus.FAILED, stage.value, validation=validation)
            stage = NodeStage.SEMANTIC_VALIDATION
            validation = self._semantic.validate(NodeValidationContext(output, identity, pass_number), registration.contract)
            if not validation.ok:
                return finish(NodeStatus.FAILED, stage.value, validation=validation)
            if task is not None and task.cancelling():
                raise asyncio.CancelledError
            return finish(NodeStatus.SUCCESS, "completed", output=output, validation=validation)
        except asyncio.CancelledError:
            return await cancelled(stage.value)
        except PythonNodeError:
            if stage not in (NodeStage.PREPARE, NodeStage.EXECUTE):
                return finish(NodeStatus.FAILED, f"{stage.value}: PythonNodeError")
            admitted: E | None = None
            try:
                # except establishes the transport class; M12 restores the
                # declared E from registered POJO classes, never the generic.
                value = cast(PythonNodeError[NodeError], sys.exception()).error
                admitted, validation = self._structural.validate_error(value, registration.contract.error_types)
                if admitted is None or not validation.ok:
                    return finish(NodeStatus.FAILED, "undeclared or malformed operation error", validation=validation)
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError
                policy = registration.contract.error_policy if apply_error_policy else None
                gate = policy(admitted) if policy is not None else None
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError
                if gate is not None:
                    gate = GateSignal.validate(gate)
                    if node.phase != ExecutionPhase.PRE_LLM:
                        raise TypeError("gate is only permitted in PRE_LLM")
            except asyncio.CancelledError:
                return await cancelled("error_policy")
            except Exception as error:
                return finish(NodeStatus.FAILED, f"error_handling: {type(error).__name__}", error=admitted)
            if gate is not None:
                return finish(NodeStatus.GATED, stage.value, gate=gate, error=admitted)
            return finish(NodeStatus.FAILED, stage.value, error=admitted)
        except Exception as error:
            return finish(NodeStatus.FAILED, f"{stage.value}: {type(error).__name__}")
