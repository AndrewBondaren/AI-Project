from time import time

from pydantic import BaseModel
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.diagnostics import ExecutionDiagnostic, ExecutionEventCode, ExecutionSeverity
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.nodeTypes.resumablePythonNode import ResumablePythonNode
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.dataModel.validation.immutableValue import validate_immutable

from app.application.engine.contracts.invocation.executionStore import RestoreFailure
from app.application.engine.contracts.invocation.nodeStep import CallGroup, Complete, NodeStep
from app.application.engine.contracts.invocation.resumeEvent import (
    CallCancelled, CallFailure, CallResults, CallRuntimeFailure, CallSuccess, ReturnedCall,
)
from app.application.engine.runtime.invocations.stepEffect import StepEffect
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.dataModel.engine.dag.identity import ExecutionId, ExecutionIdentity, InvocationId, NodeId, PlanInstanceId, PlanRevision
from app.dataModel.engine.dag.invocations.record import InvocationGraph, InvocationRecord, InvocationStatus as Status
from app.dataModel.engine.dag.records import OutputRecord


class InvocationCoordinator:
    def __init__(self, plan: ExecutionPlan, graph: InvocationGraph, limit: int):
        if limit < 1:
            raise ValueError("invocation limit must be positive")
        self.plan = plan
        self.graph = graph
        self.limit = limit
        for record in graph.records.values():
            registration = plan.registrations.get(record.node_id)
            if not registration or (registration.contract.contract_id, registration.contract.version) != (
                record.contract_id, record.version
            ):
                raise RestoreFailure("invocation contract changed")
            if record.status == Status.RUNNING:
                record.status = Status.READY

    @classmethod
    def create(cls, plan: ExecutionPlan, execution_id: ExecutionId, revision: PlanRevision,
               root: NodeId, limit: int, input: BaseModel | None):
        graph = InvocationGraph(execution_id=execution_id, revision=revision,
                                root=InvocationId(f"root/{root}"), registry=CheckpointCodec.registry(plan), records={})
        coordinator = cls(plan, graph, limit)
        record = coordinator.allocate(root, PlanInstanceId("root"))
        if input is not None:
            record.input = coordinator.encode(input, plan.registrations[root].contract.input_type)
        return coordinator

    @staticmethod
    def encode(value: BaseModel, expected: type[BaseModel]) -> str:
        if not isinstance(value, expected):
            raise TypeError("invocation payload differs from registered type")
        validate_immutable(value)
        wire = value.model_dump_json(round_trip=True)
        expected.model_validate_json(wire)
        return wire

    def allocate(self, node_id: NodeId, instance: PlanInstanceId) -> InvocationRecord:
        key = InvocationId(f"{instance}/{node_id}")
        if key in self.graph.records:
            return self.graph.records[key]
        node = self.plan.nodes[node_id].node
        deps = tuple(self.allocate(dep, instance).invocation_id for dep in node.deps)
        if len(self.graph.records) >= self.limit:
            raise ValueError("invocation limit exceeded")
        contract = self.plan.registrations[node_id].contract
        record = InvocationRecord(execution_id=self.graph.execution_id, invocation_id=key, node_id=node_id,
                                  plan_instance_id=instance, plan_revision=self.graph.revision, contract_id=contract.contract_id, version=contract.version,
                                  dependency_bindings=deps)
        self.graph.records[key] = record
        return record

    def bind_published(self, outputs: tuple[OutputRecord[BaseModel], ...]) -> None:
        root = self.graph.records[self.graph.root]
        if not outputs:
            return
        allowed = set(self.plan.prior_phase_dependencies(root.node_id))
        for output in outputs:
            identity = output.identity
            record = self.graph.records.get(identity.invocation_id)
            if (record is None or record.node_id not in allowed or identity.execution_id != self.graph.execution_id
                    or record.plan_instance_id != root.plan_instance_id or record.node_id != identity.node_id):
                raise RestoreFailure("output is not from a prior-phase dependency of this root")
            contract = self.plan.registrations[record.node_id].contract
            if (output.contract_id, output.contract_version) != (contract.contract_id, contract.version):
                raise RestoreFailure("prior-phase output contract mismatch")
            terminal = self.encode(output.output, contract.output_type)
            if record.status == Status.SUCCEEDED:
                if (record.identity() != identity or record.terminal != terminal or
                        record.reads != output.reads or record.domain_reads != output.domain_reads):
                    raise RestoreFailure("conflicting prior-phase output")
                continue
            if record.status != Status.READY:
                raise RestoreFailure("prior-phase invocation cannot accept a published result")
            record.terminal = terminal
            record.plan_revision = identity.plan_revision
            record.attempt_counter = identity.attempt
            record.reads = output.reads
            record.domain_reads = output.domain_reads
            record.status = Status.SUCCEEDED

    def next_pass(self, root: NodeId, revision: PlanRevision, reusable: set[InvocationId],
                  instance: PlanInstanceId) -> None:
        self.graph.revision = revision
        self.graph.pass_number += 1
        root_record = self.allocate(root, instance)
        self.graph.root = root_record.invocation_id
        pending = {r.invocation_id for r in self.graph.records.values()
                   if r.plan_instance_id == instance and r.invocation_id not in reusable}
        while True:
            affected = {r.invocation_id for r in self.graph.records.values() if r.plan_instance_id == instance and
                        any(read.result and read.result.invocation_id in pending for read in r.reads)}
            if affected.issubset(pending):
                break
            pending.update(affected)
        for record in self.graph.records.values():
            if record.plan_instance_id != instance or record.invocation_id not in pending:
                continue
            if record.attempt_counter:
                record.step_index += 1
            record.step_attempts = 0
            record.status = Status.READY
            record.input = None
            record.continuation = None
            record.terminal = None
            record.state_contract = None
            record.error_index = None
            record.gate_task = record.gate_reason = None
            record.reads = ()
            record.domain_reads = ()

    def children(self, parent: InvocationRecord, step: int):
        return tuple(r for r in self.graph.records.values()
                     if r.caller_invocation_id == parent.invocation_id and r.caller_step == step)

    def begin(self, record: InvocationRecord) -> None:
        if record.status != Status.READY:
            raise ValueError("attempt requires READY invocation")
        record.status = Status.RUNNING
        record.attempt_counter += 1
        record.step_attempts += 1
        record.plan_revision = self.graph.revision

    def finish(self, record: InvocationRecord, identity: ExecutionIdentity, effect: StepEffect) -> None:
        if identity != record.identity():
            raise ValueError("stale RETURN attempt")
        if record.status != Status.RUNNING:
            if isinstance(effect.step, Complete) and record.status == Status.SUCCEEDED:
                expected = self.plan.registrations[record.node_id].contract.output_type
                if record.terminal == self.encode(effect.step.output, expected):
                    return
            if effect.cancelled and record.status == Status.CANCELLED:
                return
            if effect.error is not None and record.status == Status.FAILED and record.error_index is not None:
                expected_error = self.plan.registrations[record.node_id].contract.error_types[record.error_index]
                if isinstance(effect.error, expected_error) and record.terminal == self.encode(effect.error, expected_error):
                    return
            raise ValueError("conflicting or stale RETURN")
        if record.input is None and effect.prepared is not None:
            record.input = self.encode(effect.prepared, self.plan.registrations[record.node_id].contract.input_type)
        record.diagnostics += effect.diagnostics
        record.reads += effect.reads
        record.domain_reads += effect.domain_reads
        if effect.step is not None:
            self.accept(record, effect.step)
            return
        record.status = Status.CANCELLED if effect.cancelled else Status.FAILED
        if effect.error is not None:
            contract = self.plan.registrations[record.node_id].contract
            for index, error_type in enumerate(contract.error_types):
                if isinstance(effect.error, error_type):
                    if contract.retry_policy is not None and contract.retry_policy(effect.error, record.step_attempts):
                        record.status = Status.READY
                        return
                    record.error_index = index
                    record.terminal = self.encode(effect.error, error_type)
                    break
        if effect.gate is not None and record.invocation_id == self.graph.root:
            record.gate_task = effect.gate.next_task_type.value
            record.gate_reason = effect.gate.reason

    def accept(self, parent: InvocationRecord, outcome: NodeStep[BaseModel, BaseModel]) -> None:
        contract = self.plan.registrations[parent.node_id].contract
        if isinstance(outcome, Complete):
            parent.terminal = self.encode(outcome.output, contract.output_type)
            parent.status = Status.SUCCEEDED
            return
        if contract.continuation is None:
            raise TypeError("undeclared invocation outcome")
        requests = outcome.requests if isinstance(outcome, CallGroup) else (outcome,)
        state = self.encode(outcome.state, contract.continuation.state_type)
        existing_calls = {child.call_key: child for child in self.children(parent, parent.step_index)}
        if existing_calls and (set(existing_calls) != {r.key for r in requests} or state != parent.continuation):
            raise ValueError("conflicting replay of CALL group")
        parent.state_contract = (contract.continuation.contract_id, contract.continuation.version)
        parent.continuation = state
        for request in requests:
            if request.target not in contract.calls:
                raise TypeError("undeclared CALL target")
            existing = existing_calls.get(request.key)
            if existing is not None:
                if (existing.node_id != request.target.node_id or
                        existing.input != self.encode(request.input, request.target.input_type)):
                    raise ValueError("conflicting replay of CALL key")
                continue
            child = self.allocate(request.target.node_id, PlanInstanceId(f"call-{len(self.graph.records)}"))
            child.input = self.encode(request.input, request.target.input_type)
            child.caller_invocation_id = parent.invocation_id
            child.caller_step = parent.step_index
            child.call_key = request.key
        parent.status = Status.WAITING_CALLS

    def ready(self):
        records = self.graph.records
        terminal = {Status.SUCCEEDED, Status.FAILED, Status.CANCELLED}
        changed = True
        while changed:
            changed = False
            for record in records.values():
                if record.status == Status.WAITING_CALLS and all(
                    child.status in terminal for child in self.children(record, record.step_index)
                ):
                    changed = True
                    record.step_index += 1
                    record.step_attempts = 0
                    record.status = Status.READY
                if record.status != Status.READY:
                    continue
                failed = next((records[key] for key in record.dependency_bindings
                               if records[key].status in (Status.FAILED, Status.CANCELLED)), None)
                if failed is not None:
                    changed = True
                    record.status = Status.FAILED
                    record.attempt_counter = max(record.attempt_counter, 1)
                    node = self.plan.nodes[record.node_id].node
                    if not isinstance(node, (PythonNode, ResumablePythonNode)):
                        raise TypeError("unsupported invocation binding")
                    record.diagnostics += (ExecutionDiagnostic(
                        identity=record.identity(), phase=node.phase, pass_number=self.graph.pass_number,
                        level=0, timestamp=time(), code=ExecutionEventCode.NODE_FINISHED,
                        severity=ExecutionSeverity.ERROR, status=NodeStatus.FAILED,
                        message=f"prerequisite {failed.invocation_id} ended with {failed.status}",
                    ),)
        return tuple(r for r in records.values() if r.status == Status.READY and
                     all(records[k].status == Status.SUCCEEDED for k in r.dependency_bindings))

    def view(self, record: InvocationRecord):
        outputs: dict[NodeId, OutputRecord[BaseModel]] = {}
        for key in record.dependency_bindings:
            dep = self.graph.records[key]
            contract = self.plan.registrations[dep.node_id].contract
            outputs[dep.node_id] = OutputRecord[BaseModel](
                identity=dep.identity(), contract_id=dep.contract_id, contract_version=dep.version,
                output=contract.output_type.model_validate_json(dep.terminal_payload()), reads=dep.reads, domain_reads=dep.domain_reads,
            )
        contract = self.plan.registrations[record.node_id].contract
        return PublishedDAGReadView(record.node_id, contract.reads, self.plan.registrations, outputs, record.execution_id)

    def event(self, parent: InvocationRecord) -> CallResults:
        entries: list[ReturnedCall] = []
        calls = self.plan.registrations[parent.node_id].contract.calls
        for child in self.children(parent, parent.step_index - 1):
            if child.call_key is None:
                raise ValueError("missing return address")
            target = next(t for t in calls if t.node_id == child.node_id)
            if child.status == Status.SUCCEEDED:
                result = CallSuccess(target.output_type.model_validate_json(child.terminal_payload()))
            elif child.status == Status.CANCELLED:
                result = CallCancelled()
            elif child.error_index is not None:
                result = CallFailure(target.error_types[child.error_index].model_validate_json(child.terminal_payload()))
            else:
                result = CallRuntimeFailure(child.identity())
            entries.append(ReturnedCall(child.call_key, target, result))
        return CallResults(tuple(entries))
