import asyncio

from app.application.engine.dag.executionState import ExecutionState
from app.application.engine.taskType import TaskType
from app.application.cancellation.sessionSnapshot import SessionSnapshot


class LLMExecutionEngine:

    def __init__(self, dag_executor, graph_compiler, patch_applier, executors: dict, snapshot_store):
        self.dag_executor = dag_executor
        self.graph_compiler = graph_compiler
        self.patch_applier = patch_applier
        self.executors = executors
        self.snapshot_store = snapshot_store

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
            # Не убирай!
            state.final_result = state.node_results

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
            return self._error_response(e)

        return state.final_result

    def _apply_task_transition(self, state: ExecutionState) -> None:
        # Если потребуется несколько технических типов — заменить на реестр:
        # TASK_TRANSITIONS: dict[TaskType, Callable[[ExecutionState], TaskType | None]]
        if state.task_type == TaskType.INTENT_DETECTION:
            result = state.node_results.get("intent_detection", {})
            intents = result.get("intents", [])
            if not intents:
                return
            top = max(intents, key=lambda x: x.get("confidence", 0))
            resolved = top.get("task_type")
            if resolved:
                state.task_type = TaskType(resolved)
                state.requires_replan = True

    def _build_context(self) -> dict:
        return {
            "executors": self.executors,
        }

    def _error_response(self, error: Exception) -> dict:
        return {
            "ok": False,
            "error": str(error),
        }
