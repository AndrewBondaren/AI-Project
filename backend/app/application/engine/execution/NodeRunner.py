from datetime import datetime, timezone

from app.application.engine.dag.executionTrace import ExecutionTrace
from app.application.engine.nodes.nodeRegistry import NODE_REGISTRY


class NodeRunner:

    def __init__(self, node_validator):
        self.node_validator = node_validator

    async def run(self, compiled_node, state, context) -> object:
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

            result = await executor.execute(node, state, context)

            result, ok = await self.node_validator.validate_with_repair(node, result, state)

            if not ok:
                state.node_status[node.id] = "failed"
                trace.status = "failed"
                trace.error = state.node_errors.get(node.id, [{}])[-1].get("error")
                return None

            state.node_status[node.id] = "success"
            state.node_results[node.id] = result
            trace.output = result
            trace.status = "success"

            return result

        except Exception as e:
            state.node_status[node.id] = "failed"
            state.node_errors.setdefault(node.id, []).append({"error": str(e)})
            trace.status = "failed"
            trace.error = str(e)
            return None

        finally:
            trace.end_time = datetime.now(timezone.utc)
            state.traces.append(trace)