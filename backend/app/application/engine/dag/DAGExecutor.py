import asyncio

from app.application.engine.dag.stateSnapshot import StateSnapshot


class DAGExecutor:

    def __init__(self, node_runner, llm_aggregate_executor):
        self.node_runner = node_runner
        self.llm_aggregate_executor = llm_aggregate_executor

    async def execute(self, plan, state, context) -> object:

        # Фаза 1: pre_llm Python-ноды
        await self._execute_phase(plan.pre_llm_levels, plan, state, context, phase="pre_llm")

        # Фаза 2: LLM-группы ASC по temperature
        for llm_group in plan.llm_groups:
            await self.llm_aggregate_executor.execute(llm_group, plan, state, context)

        # Фаза 3: post_llm Python-ноды
        await self._execute_phase(plan.post_llm_levels, plan, state, context, phase="post_llm")

        state.final_result = state.node_results

        return state

    # --------------------------------------------------

    async def _execute_phase(self, levels, plan, state, context, phase: str):
        for level_idx, level in enumerate(levels):
            await self._run_level(level, plan, state, context)
            self._create_snapshot(state, phase=phase, level_idx=level_idx)

    async def _run_level(self, level, plan, state, context):
        tasks = [
            self.node_runner.run(plan.nodes[node_id], state, context)
            for node_id in level
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for node_id, result in zip(level, results):
            if isinstance(result, Exception):
                state.node_status[node_id] = "failed"
                state.node_errors.setdefault(node_id, []).append({
                    "error": str(result)
                })

    def _create_snapshot(self, state, phase: str, level_idx: int):
        snapshot = StateSnapshot(
            level=level_idx,
            node_results=dict(state.node_results),
            node_status=dict(state.node_status),
            shared_context=dict(state.shared_context),
            execution_order=list(state.execution_order),
        )
        state.snapshots.append(snapshot)