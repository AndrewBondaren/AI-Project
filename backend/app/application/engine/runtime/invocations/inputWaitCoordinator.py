import json

from pydantic import BaseModel

from app.application.engine.contracts.invocation.inputWait import (
    InputConflict, InputReceived, InputWaitContract, InteractionPort, PendingInput, ResumeInput, Waiting, WaitSpec,
)
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.dataModel.engine.dag.invocations.inputWait import AcceptedInput, InputReceipt, SavedWait
from app.dataModel.engine.dag.invocations.record import InvocationGraph, InvocationRecord, InvocationStatus
from app.dataModel.validation.immutableValue import validate_immutable


class InputWaitCoordinator:
    @staticmethod
    def check_owner(graph: InvocationGraph, port: InteractionPort | None) -> InteractionPort:
        if port is None or graph.interaction_owner is None or port.owner != graph.interaction_owner:
            raise PermissionError("execution belongs to a different interaction")
        return port

    @staticmethod
    def encode(value: BaseModel, expected: type[BaseModel]) -> str:
        if type(value) is not expected:
            raise TypeError("interaction payload differs from its declared type")
        validate_immutable(value)
        wire = value.model_dump_json(round_trip=True)
        expected.model_validate_json(wire)
        return json.dumps(json.loads(wire), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def open(cls, graph: InvocationGraph, record: InvocationRecord, spec: WaitSpec[BaseModel, BaseModel],
             declared: InputWaitContract[BaseModel, BaseModel] | None, port: InteractionPort | None) -> None:
        trusted = cls.check_owner(graph, port)
        if spec.contract != declared or spec.wait_id in graph.waits:
            raise InputConflict("undeclared input contract or reused wait id")
        binding = trusted.bind(spec.binding_ref, record.identity(), record.step_index)
        if binding.owner != trusted.owner or binding.reference != spec.binding_ref:
            raise PermissionError("interaction binding does not match execution")
        if binding.revision != spec.expected_revision:
            raise InputConflict("interaction revision changed before wait")
        graph.waits[spec.wait_id] = SavedWait(
            wait_id=spec.wait_id, invocation_id=record.invocation_id, step_index=record.step_index,
            contract_id=spec.contract.contract_id, version=spec.contract.version, binding=binding,
            intermediate=cls.encode(spec.intermediate, spec.contract.intermediate_type),
        )
        record.status = InvocationStatus.WAITING_INPUT

    @staticmethod
    def contract(graph: InvocationGraph, plan: ExecutionPlan, wait: SavedWait) -> InputWaitContract[BaseModel, BaseModel]:
        record = graph.records[wait.invocation_id]
        contract = plan.registrations[record.node_id].contract.input_wait
        if contract is None or (contract.contract_id, contract.version) != (wait.contract_id, wait.version):
            raise ValueError("input wait contract changed")
        return contract

    @classmethod
    def accept[U: BaseModel](cls, graph: InvocationGraph, plan: ExecutionPlan, request: ResumeInput[U],
               port: InteractionPort | None) -> tuple[InputReceipt, bool]:
        trusted = cls.check_owner(graph, port)
        wait = graph.waits.get(request.wait_id)
        if wait is None or graph.cancellation is not None or request.expected_revision != wait.binding.revision:
            raise InputConflict("unknown, cancelled or stale wait")
        payload = cls.encode(request.payload, cls.contract(graph, plan, wait).input_type)
        if wait.accepted is not None:
            accepted = wait.accepted
            if accepted.receipt.request_id == request.request_id and accepted.payload == payload:
                return accepted.receipt, False
            raise InputConflict("wait already consumed")
        if any(w.accepted and w.accepted.receipt.request_id == request.request_id for w in graph.waits.values()):
            raise InputConflict("request id already used")
        record = graph.records[wait.invocation_id]
        if record.status != InvocationStatus.WAITING_INPUT or record.step_index != wait.step_index:
            raise InputConflict("input is out of order")
        trusted.authorize(wait.binding, request.payload)
        receipt = InputReceipt(wait_id=wait.wait_id, request_id=request.request_id, revision=wait.binding.revision + 1)
        accepted = AcceptedInput(payload=payload, receipt=receipt)
        graph.waits[wait.wait_id] = wait.model_copy(update={"accepted": accepted})
        graph.waiting_for_input = False
        record.step_index += 1
        record.step_attempts = 0
        record.status = InvocationStatus.READY
        return receipt, True

    @classmethod
    def event(cls, graph: InvocationGraph, plan: ExecutionPlan, record: InvocationRecord) -> InputReceived[BaseModel] | None:
        for wait in graph.waits.values():
            if wait.invocation_id == record.invocation_id and wait.step_index + 1 == record.step_index and wait.accepted:
                contract = cls.contract(graph, plan, wait)
                return InputReceived(contract, contract.input_type.model_validate_json(wait.accepted.payload))
        return None

    @classmethod
    def validate(cls, graph: InvocationGraph, plan: ExecutionPlan) -> None:
        pending: set[str] = set()
        requests: set[str] = set()
        steps: set[tuple[str, int]] = set()
        for key, wait in graph.waits.items():
            record = graph.records[wait.invocation_id]
            step = (wait.invocation_id, wait.step_index)
            if key != wait.wait_id or wait.binding.owner != graph.interaction_owner or step in steps:
                raise ValueError("invalid persisted wait binding")
            steps.add(step)
            contract = cls.contract(graph, plan, wait)
            contract.intermediate_type.model_validate_json(wait.intermediate)
            if wait.accepted is not None:
                receipt = wait.accepted.receipt
                if (receipt.wait_id != key or receipt.request_id in requests or receipt.revision != wait.binding.revision + 1
                        or wait.step_index >= record.step_index):
                    raise ValueError("invalid persisted input receipt")
                requests.add(receipt.request_id)
                if (record.step_index == wait.step_index + 1
                        and record.status in (InvocationStatus.READY, InvocationStatus.RUNNING)
                        and record.continuation is None):
                    raise ValueError("accepted input has no continuation")
                contract.input_type.model_validate_json(wait.accepted.payload)
            elif record.status != InvocationStatus.CANCELLED or graph.cancellation is None:
                if wait.step_index != record.step_index or record.continuation is None:
                    raise ValueError("invalid pending continuation")
                pending.add(record.invocation_id)
        if pending != {r.invocation_id for r in graph.records.values() if r.status == InvocationStatus.WAITING_INPUT}:
            raise ValueError("input wait differs from invocation state")
        if graph.waiting_for_input and (not pending or any(
            r.status == InvocationStatus.RUNNING or (r.status == InvocationStatus.READY and all(
                graph.records[key].status == InvocationStatus.SUCCEEDED for key in r.dependency_bindings
            )) for r in graph.records.values()
        )):
            raise ValueError("invalid waiting execution")

    @classmethod
    def waiting(cls, graph: InvocationGraph, plan: ExecutionPlan) -> Waiting[BaseModel]:
        return Waiting(tuple(PendingInput(w.wait_id, w.binding.revision,
                             cls.contract(graph, plan, w).intermediate_type.model_validate_json(w.intermediate))
                             for w in graph.waits.values() if w.accepted is None and
                             graph.records[w.invocation_id].status == InvocationStatus.WAITING_INPUT))
