import asyncio
from datetime import datetime, timezone

from app.application.engine.dag.stateSnapshot import StateSnapshot
from app.application.engine.dag.executionTrace import ExecutionTrace
from app.application.engine.nodes.nodeRegistry import NODE_REGISTRY
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus


class DAGExecutor:

    def __init__(self, validator, repair_orchestrator):
        self.validator = validator
        self.repair = repair_orchestrator

    async def execute(self, plan, state, context) -> object:

        self.context = context

        for level_idx, level in enumerate(plan.levels):
            await self._execute_level(level, plan, state, level_idx)

        state.final_result = state.node_results

        return state

    # --------------------------------------------------

    async def _execute_level(self, level, plan, state, level_idx):
        await self._run_nodes(level, plan, state)
        self._create_snapshot(state, level_idx)

    async def _run_nodes(self, level, plan, state):

        tasks = [
            self._execute_node(plan.nodes[node_id], state)
            for node_id in level
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for node_id, result in zip(level, results):
            if isinstance(result, Exception):
                self._handle_failure(node_id, result, state)

    async def _execute_node(self, compiled_node, state):

        node = compiled_node.node
        state.node_status[node.id] = "running"
        state.execution_order.append(node.id)

        trace = ExecutionTrace(
            node_id=node.id,
            start_time=datetime.now(timezone.utc),
            input=dict(state.node_results)
        )

        try:
            registration = NODE_REGISTRY.get(node.id)
            executor = self.context["executors"][registration.executor_cls]

            result = await executor.execute(node, state, self.context)

            validation = self.validator.validate(
                node=node,
                output=result,
                state=state,
            )

            if not validation.ok:
                result, validation = await self._retry_until_valid(
                    node=node,
                    output=result,
                    validation=validation,
                    state=state,
                )

            if not validation.ok:
                state.node_status[node.id] = "failed"
                trace.status = "failed"
                trace.error = validation.reason
                self._record_validation_failure(node.id, validation, state)
                return None

            state.node_status[node.id] = "success"
            state.node_results[node.id] = result
            trace.output = result
            trace.status = "success"

            return result

        except Exception as e:
            self._handle_failure(node.id, e, state)
            trace.status = "failed"
            trace.error = str(e)
            return None

        finally:
            trace.end_time = datetime.now(timezone.utc)
            state.traces.append(trace)

    # --------------------------------------------------

    def _create_snapshot(self, state, level_idx):

        snapshot = StateSnapshot(
            level=level_idx,
            node_results=dict(state.node_results),
            node_status=dict(state.node_status),
            shared_context=dict(state.shared_context),
            execution_order=list(state.execution_order),
        )

        state.snapshots.append(snapshot)

    def _handle_failure(self, node_id, error, state):

        state.node_status[node_id] = "failed"
        state.node_errors.setdefault(node_id, []).append({
            "error": str(error)
        })

    async def _retry_until_valid(self, node, output, validation, state):

        max_attempts = state.session.repair_iterations
        attempt = 0

        while not validation.ok:
            if validation.failed:
                return output, validation

            if attempt >= max_attempts:
                return output, ValidationResult(
                    status=ValidationStatus.FAIL,
                    reason=f"repair_limit_exceeded: {max_attempts}",
                )

            if not node.retry_policy or not node.retry_policy.get("enabled"):
                return output, validation

            repaired = await self.repair.repair_node(
                node=node,
                output=output,
                reason=validation.reason,
                state=state,
            )
            attempt += 1

            if repaired is None:
                return output, validation

            output = repaired
            validation = self.validator.validate(
                node=node,
                output=output,
                state=state,
            )

        return output, validation

    def _record_validation_failure(self, node_id, validation, state):

        state.node_errors.setdefault(node_id, []).append({
            "status": validation.status.value,
            "error": validation.reason,
        })