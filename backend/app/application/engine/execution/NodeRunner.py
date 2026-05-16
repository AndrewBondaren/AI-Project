from datetime import datetime, timezone

from app.application.engine.dag.executionTrace import ExecutionTrace
from app.application.engine.nodes.nodeRegistry import NODE_REGISTRY
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.validation.nodeValidationContext import NodeValidationContext


class NodeRunner:

    def __init__(self, node_validator):
        self.node_validator = node_validator

    async def run(self, compiled_node, state, context) -> NodeResult | None:
        """
        Выполняет одну Python-ноду:
          - открывает трейс
          - вызывает executor из context["executors"]
          - валидирует результат через NodeValidator
          - пишет статус и результат в state
          - закрывает трейс
        """
        node = compiled_node.node
        state.node_status[node.id] = "running"
        state.execution_order.append(node.id)

        trace = ExecutionTrace(
            node_id=node.id,
            start_time=datetime.now(timezone.utc),
            input=dict(state.node_results),
            output=None,
        )

        try:
            registration = NODE_REGISTRY.get(node.id)
            executor = context["executors"][registration.executor_cls]

            node_result: NodeResult = await executor.execute(node, state, context)

            ctx = NodeValidationContext(
                node=node,
                output=node_result.data,
                state=state,
            )
            validation = self.node_validator.validate(ctx)

            if not validation.ok:
                state.node_status[node.id] = "failed"
                state.node_errors.setdefault(node.id, []).append({
                    "status": validation.status.value,
                    "errors": [e.code for e in validation.errors],
                })
                trace.status = "failed"
                trace.error = validation.reason
                return None

            state.node_status[node.id] = "success"
            state.node_results[node.id] = node_result.data
            trace.output = node_result.data
            trace.status = "success"

            return node_result

        except Exception as e:
            state.node_status[node.id] = "failed"
            state.node_errors.setdefault(node.id, []).append({"error": str(e)})
            trace.status = "failed"
            trace.error = str(e)
            return None

        finally:
            trace.end_time = datetime.now(timezone.utc)
            state.traces.append(trace)