from app.dataModel.engine.dag.identity import CallKey, InvocationId

from app.application.engine.contracts.invocation.executionStore import RestoreFailure
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.dataModel.engine.dag.invocations.record import InvocationGraph, InvocationStatus, RegisteredContract


class CheckpointCodec:
    @staticmethod
    def registry(plan: ExecutionPlan) -> tuple[RegisteredContract, ...]:
        return tuple(RegisteredContract(node_id=node, contract_id=c.contract_id, version=c.version,
                                       continuation=(c.continuation.contract_id, c.continuation.version)
                                       if c.continuation else None)
                     for node in sorted(plan.registrations) for c in (plan.registrations[node].contract,))

    @staticmethod
    def encode(graph: InvocationGraph) -> bytes:
        return graph.model_dump_json().encode()

    @classmethod
    async def restore(cls, blob: bytes, plan: ExecutionPlan) -> InvocationGraph:
        graph = cls.decode(blob, plan)
        for record in graph.records.values():
            contract = plan.registrations[record.node_id].contract
            if record.status == InvocationStatus.SUCCEEDED and contract.lifecycle is not None:
                try:
                    await contract.lifecycle.validate_restored(contract.output_type.model_validate_json(record.terminal_payload()))
                except Exception as exc:
                    raise RestoreFailure(f"rejected restored output of {record.invocation_id}") from exc
        return graph

    @staticmethod
    def decode(blob: bytes, plan: ExecutionPlan) -> InvocationGraph:
        try:
            graph = InvocationGraph.model_validate_json(blob)
            if graph.registry != CheckpointCodec.registry(plan):
                raise ValueError("registered contracts changed")
            if graph.root not in graph.records:
                raise ValueError("missing root invocation")
            dispatches: set[tuple[InvocationId, int, CallKey]] = set()
            for key, record in graph.records.items():
                contract = plan.registrations[record.node_id].contract
                if record.execution_id != graph.execution_id or key != record.invocation_id:
                    raise ValueError("incompatible invocation address")
                if key != f"{record.plan_instance_id}/{record.node_id}":
                    raise ValueError("incompatible instance binding")
                if (record.contract_id, record.version) != (contract.contract_id, contract.version):
                    raise ValueError("contract version changed")
                if record.input is not None:
                    contract.input_type.model_validate_json(record.input)
                if record.continuation is not None:
                    continuation = contract.continuation
                    if continuation is None or (continuation.contract_id, continuation.version) != record.state_contract:
                        raise ValueError("continuation contract changed")
                    continuation.state_type.model_validate_json(record.continuation)
                if record.status == InvocationStatus.SUCCEEDED:
                    if record.terminal is None:
                        raise ValueError("missing terminal output")
                    contract.output_type.model_validate_json(record.terminal)
                if record.error_index is not None:
                    if record.terminal is None:
                        raise ValueError("missing terminal error")
                    contract.error_types[record.error_index].model_validate_json(record.terminal)
                if record.caller_invocation_id is not None:
                    parent = graph.records[record.caller_invocation_id]
                    if record.call_key is None or record.caller_step is None or record.caller_step > parent.step_index:
                        raise ValueError("invalid caller continuation")
                    dispatch = (parent.invocation_id, record.caller_step, record.call_key)
                    if dispatch in dispatches or parent.plan_instance_id == record.plan_instance_id:
                        raise ValueError("duplicate or unscoped dispatch")
                    dispatches.add(dispatch)
                    if not any(t.node_id == record.node_id for t in plan.registrations[parent.node_id].contract.calls):
                        raise ValueError("undeclared persisted CALL")
                elif record.call_key is not None or record.caller_step is not None:
                    raise ValueError("partial caller binding")
                if record.status == InvocationStatus.WAITING_CALLS and not any(
                    child.caller_invocation_id == key and child.caller_step == record.step_index
                    for child in graph.records.values()
                ):
                    raise ValueError("empty persisted join")
                dependencies = tuple(graph.records[k] for k in record.dependency_bindings)
                if not record.accepts_reads(record.reads):
                    raise ValueError("foreign dependency read")
                if any(dep.plan_instance_id != record.plan_instance_id for dep in dependencies):
                    raise ValueError("cross-instance dependency binding")
                if tuple(dep.node_id for dep in dependencies) != plan.nodes[record.node_id].node.deps:
                    raise ValueError("dependency bindings changed")
            return graph
        except (ValueError, KeyError, IndexError) as exc:
            raise RestoreFailure("invalid invocation checkpoint") from exc
