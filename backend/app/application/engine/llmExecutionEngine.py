import asyncio

from app.application.engine.dag.executionState import ExecutionState
from app.application.engine.taskType import TaskType
from app.application.cancellation.sessionSnapshot import SessionSnapshot


class LLMExecutionEngine:

    def __init__(self, dag_executor, graph_compiler, patch_applier, executors: dict, snapshot_store, response_resolver, repositories: dict | None = None):
        self.dag_executor = dag_executor
        self.graph_compiler = graph_compiler
        self.patch_applier = patch_applier
        self.executors = executors
        self.snapshot_store = snapshot_store
        self.response_resolver = response_resolver
        self._repositories = repositories or {}

    async def run(self, task_type, message, session, cancel_token=None, snapshot=None):

        if snapshot:
            state = ExecutionState(snapshot.original_message, session)
            state.task_type = TaskType(snapshot.task_type)
            state.node_results = dict(snapshot.node_results)
            state.node_status = dict(snapshot.node_status)
        else:
            state = ExecutionState(message, session)
            state.task_type = task_type

        state.cancel_token = cancel_token

        try:
            for pass_num in range(session.max_passes):

                state.pass_number = pass_num

                #Compile
                plan = self.graph_compiler.compile(state)
                #Execute DAG
                state = await self.dag_executor.execute(
                    plan=plan,
                    state=state,
                    context=self._build_context(),
                )

                self._apply_task_transition(state)

                if not state.requires_replan:
                    break

            # все passes завершены — применяем патчи атомарно
            self.patch_applier.apply(state)

            # извлекаем user-facing ответ из node_results
            resolved = self.response_resolver.resolve(state)
            if not resolved.ok:
                return {"ok": False, "error": resolved.error}

            # Не убирай!
            state.final_result = resolved.data

        except asyncio.CancelledError:
            snap = SessionSnapshot(
                session_id=state.session.session_id,
                node_results=dict(state.node_results),
                node_status=dict(state.node_status),
                task_type=state.task_type.value if state.task_type else "",
                original_message=state.message,
            )
            self.snapshot_store.save(snap)
            raise

        except Exception as e:
            return self._error_response(e, state=state)

        return state.final_result

    def _apply_task_transition(self, state: ExecutionState) -> None:
        # Если потребуется несколько технических типов — заменить на реестр:
        # TASK_TRANSITIONS: dict[TaskType, Callable[[ExecutionState], TaskType | None]]
        if state.task_type == TaskType.INTENT_DETECTION:
            # Приоритет 1: Python-нода (pre_llm) задекларировала явный переход.
            # Например, check_scene не нашла сцену → next_task_type=SCENE_INIT.
            # В этом случае LLM не вызывался, intent_detection результата нет.
            if state.next_task_type is not None:
                state.task_type = state.next_task_type
                state.next_task_type = None
                state.requires_replan = True
                return

            # Приоритет 2: LLM вернул интенты → выбираем наиболее уверенный.
            result = state.node_results.get("intent_detection", {})
            intents = result.get("intents", [])
            if not intents:
                return
            top = max(intents, key=lambda x: x.get("confidence", 0))
            resolved = top.get("task_type")
            if resolved:
                state.task_type = TaskType(resolved)
                state.requires_replan = True

        elif state.next_task_type is not None:
            # Python-нода задекларировала явный переход для не-технических task_type
            state.task_type = state.next_task_type
            state.next_task_type = None
            state.requires_replan = True

    def _build_context(self) -> dict:
        return {
            "executors": self.executors,
            **self._repositories,
        }

    def _error_response(self, error: Exception, state=None) -> dict:
        # Если нода задекларировала user_message — показываем его, а не технический текст
        if state is not None and state.user_error:
            return {"ok": False, "error": state.user_error}
        return {"ok": False, "error": str(error)}
