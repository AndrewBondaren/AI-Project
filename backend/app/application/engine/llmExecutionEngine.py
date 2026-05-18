from app.application.engine.dag.executionState import ExecutionState


class LLMExecutionEngine:

    def __init__(self, dag_executor, graph_compiler, patch_applier, executors: dict):
        self.dag_executor = dag_executor
        self.graph_compiler = graph_compiler
        self.patch_applier = patch_applier
        self.executors = executors

    async def run(self, task_type, message, session):

        state = ExecutionState(message, session)
        state.task_type = task_type

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

                if not state.requires_replan:
                    break

            # все passes завершены — применяем патчи атомарно
            self.patch_applier.apply(state)
            #apply changes
            state.final_result = state.node_results

        except Exception as e:
            return self._error_response(e)

        return state.final_result

    def _build_context(self) -> dict:
        return {
            "executors": self.executors,
        }

    def _error_response(self, error: Exception) -> dict:
        return {
            "ok": False,
            "error": str(error),
        }