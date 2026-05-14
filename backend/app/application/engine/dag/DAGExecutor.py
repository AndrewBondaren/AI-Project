import asyncio
from datetime import datetime, timezone

from app.application.engine.dag.stateSnapshot import StateSnapshot
from app.application.engine.dag.DAGexecutionTrace import ExecutionTrace


class DAGExecutor:

    async def execute(self, graph, state, context):

        self.registry = context["node_executor_registry"]
        self.validator = context["contract_validator"]
        self.repair = context["repair_orchestrator"]
        self.context = context

        for level in graph.levels:

            await self.execute_level(self, level, graph, state, level_idx)

        state.final_result = state.node_results

        return state

    async def _run_nodes(self, level, graph, state):

        tasks = [
            self.execute_node(graph.nodes[node_id], state)
            for node_id in level
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for node_id, result in zip(level, results):

            if isinstance(result, Exception):
                self.handle_failure(node_id, result, state)

    async def execute_level(self, level, graph, state, level_idx):

        await self._run_nodes(level, graph, state)

        self.create_snapshot(state, level_idx)

    def create_snapshot(self, state, level_idx):

        snapshot = StateSnapshot(
            level=level_idx,
            node_results=dict(state.node_results),
            node_status=dict(state.node_status),
            shared_context=dict(state.shared_context),
            execution_order=list(state.execution_order),
        )

        state.snapshots.append(snapshot)

    async def execute_node(self, node, state):

        state.node_status[node.id] = "running"

        trace = ExecutionTrace(
            node_id=node.id,
            start_time=datetime.now(timezone.utc),
            input=dict(state.node_results)
        )

        try:

            executor = self.registry.get(node.executor_class)

            result = await executor.execute(node, state, self.context)

            validation = self.validator.validate(
             output=result,
                contract=node.contract
            )

            if not validation.ok:
                state.node_status[node.id] = "failed"

                if result is None:
                    state.node_status[node.id] = "failed"
                    return None

            state.node_status[node.id] = "success"
            state.node_results[node.id] = result

            return result

        except Exception as e:

            return self.handle_exception(node, e, state)

        finally:
            trace.end_time = datetime.now(timezone.utc)
            state.traces.append(trace)

    def handle_failure(self, node_id, error, state):

        state.node_status[node_id] = "failed"

        state.node_errors.setdefault(node_id, []).append({
            "error": str(error)
        })

    def trigger_retry(self, node, output, validation, state):

        if not node.retry_policy or not node.retry_policy.get("enabled"):
            return None

        return self.repair.repair_node(
            node=node,
            output=output,
            reason=validation.reason,
            state=state
        )