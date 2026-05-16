import asyncio

from app.application.engine.dag.stateSnapshot import StateSnapshot
from app.application.engine.nodes.pojo.nodeResult import NodeResult


class DAGExecutor:

    def __init__(self, node_runner, llm_aggregate_executor):
        self.node_runner = node_runner
        self.llm_aggregate_executor = llm_aggregate_executor

    async def execute(self, plan, state, context) -> object:

        # сбрасываем флаг перед каждым pass
        state.requires_replan = False
        state.replan_reason = None

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
            node_results = await self._run_level(level, plan, state, context)
            self._aggregate_replan(node_results, state)
            self._create_snapshot(state, phase=phase, level_idx=level_idx)

    async def _run_level(self, level, plan, state, context) -> list:
        tasks = [
            self.node_runner.run(plan.nodes[node_id], state, context)
            for node_id in level
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Exception от asyncio.gather — нода упала вне try/except NodeRunner
        for node_id, result in zip(level, results):
            if isinstance(result, Exception):
                state.node_status[node_id] = "failed"
                state.node_errors.setdefault(node_id, []).append({
                    "error": str(result)
                })

        return [r for r in results if isinstance(r, NodeResult)]
    
    def _aggregate_replan(self, node_results: list, state):
        """
        Если хоть одна нода уровня вернула requires_replan=True —
        выставляем флаг на state. Нода декларирует намерение,
        DAGExecutor агрегирует.
        """
        for node_result in node_results:
            if node_result.requires_replan:
                state.requires_replan = True
                if node_result.replan_reason:
                    state.replan_reason = node_result.replan_reason
                break

    def _create_snapshot(self, state, phase: str, level_idx: int):
        snapshot = StateSnapshot(
            level=level_idx,
            node_results=dict(state.node_results),
            node_status=dict(state.node_status),
            shared_context=dict(state.shared_context),
            execution_order=list(state.execution_order),
        )
        state.snapshots.append(snapshot)