import asyncio

from app.application.engine.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.events.eventBus import emit
from app.application.events.sseEvents import NodeStatusEvent, NodePhase


class DAGExecutor:

    def __init__(self, node_runner, llm_aggregate_executor):
        self.node_runner = node_runner
        self.llm_aggregate_executor = llm_aggregate_executor

    async def execute(self, plan, state, context) -> object:

        # сбрасываем флаги перед каждым pass
        state.requires_replan = False
        state.replan_reason = None
        state.next_task_type = None

        # Фаза 1: pre_llm Python-ноды
        await self._execute_phase(plan.pre_llm_levels, plan, state, context, phase="pre_llm")

        # Gate-нода сигнализировала replan — прерываем до LLM, движок перекомпилирует
        if state.requires_replan:
            return state

        # Фаза 2: LLM-группы ASC по temperature
        for llm_group in plan.llm_groups:
            node_ids = [nid for level in llm_group.levels for nid in level]

            if state.cancel_token and state.cancel_token.is_cancelled():
                raise asyncio.CancelledError()

            # skip group if all nodes already completed (resume)
            if all(nid in state.node_results for nid in node_ids):
                continue

            task_type = state.task_type.value
            for nid in node_ids:
                await emit(NodeStatusEvent(node_id=nid, task_type=task_type, phase=NodePhase.EXECUTING))
            await self.llm_aggregate_executor.execute(llm_group, plan, state, context)
            for nid in node_ids:
                phase = NodePhase.DONE if state.node_status.get(nid) == "success" else NodePhase.FAILED
                await emit(NodeStatusEvent(node_id=nid, task_type=task_type, phase=phase))

        # Фаза 3: post_llm Python-ноды
        await self._execute_phase(plan.post_llm_levels, plan, state, context, phase="post_llm")

        return state

    # --------------------------------------------------

    async def _execute_phase(self, levels, plan, state, context, phase: str):
        for level_idx, level in enumerate(levels):
            await self._run_level(level, plan, state, context)

            # Python-нода не LLM: нет retry, нет repair. Упала — это баг или инфра.
            # Продолжать выполнение нельзя: gate-ноды не проверены, state не собран.
            failed = [
                nid for nid in level
                if state.node_status.get(nid) == "failed"
            ]
            if failed:
                errors = {nid: state.node_errors.get(nid, []) for nid in failed}
                raise RuntimeError(
                    f"Python nodes failed in '{phase}' phase: {failed}. Errors: {errors}"
                )

            self._create_snapshot(state, phase=phase, level_idx=level_idx)

    def _should_skip(self, node_id: str, plan, state) -> bool:
        if node_id not in state.node_results:
            return False
        if state.pass_number == 0:
            return True  # pass 0: resume-логика — пропускаем уже выполненные
        # replan pass: gate-ноды с внешним состоянием перезапускаем
        node = plan.nodes[node_id].node
        return getattr(node, 'skip_on_replan', True)

    async def _run_level(self, level, plan, state, context) -> list:
        if state.cancel_token and state.cancel_token.is_cancelled():
            raise asyncio.CancelledError()

        to_run = [nid for nid in level if not self._should_skip(nid, plan, state)]
        if not to_run:
            return []

        task_type = state.task_type.value
        for node_id in to_run:
            await emit(NodeStatusEvent(node_id=node_id, task_type=task_type, phase=NodePhase.EXECUTING))

        tasks = [
            self.node_runner.run(plan.nodes[node_id], state, context)
            for node_id in to_run
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Exception от asyncio.gather — нода упала вне try/except NodeRunner
        for node_id, result in zip(to_run, results):
            if isinstance(result, Exception):
                state.node_status[node_id] = "failed"
                state.node_errors.setdefault(node_id, []).append({
                    "error": str(result)
                })
                await emit(NodeStatusEvent(node_id=node_id, task_type=task_type, phase=NodePhase.FAILED))
            else:
                await emit(NodeStatusEvent(node_id=node_id, task_type=task_type, phase=NodePhase.DONE))

        return results

    #_create_snapshot — делает dict(state.node_results) и list(state.execution_order) — это shallow copy. Для node_results это потенциально важно: если значения в dict сами являются мутируемыми объектами (например, вложенные dict от LLM), снапшот будет держать ссылки на те же объекты. Сейчас не проблема, но когда появятся post_llm ноды, мутирующие содержимое результатов — снапшот незаметно изменится вместе с ними. Стоит иметь в виду к моменту реализации
    def _create_snapshot(self, state, phase: str, level_idx: int):
        snapshot = ExecutionLevelSnapshot(
            phase=phase,
            level=level_idx,
            node_results=dict(state.node_results),
            node_status=dict(state.node_status),
            shared_context=dict(state.shared_context),
            execution_order=list(state.execution_order),
        )
        state.snapshots.append(snapshot)
