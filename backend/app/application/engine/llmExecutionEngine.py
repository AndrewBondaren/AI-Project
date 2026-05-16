from app.application.engine.dag.executionState import ExecutionState


class LLMExecutionEngine:

    def __init__(
        self,
        dag_executor,
        graph_compiler,
        executors: dict,
    ):
        self.dag_executor = dag_executor
        self.graph_compiler = graph_compiler
        self.executors = executors

    async def run(self, task_type, message, session):

        state = ExecutionState(message, session)
        state.task_type = task_type

        # COMPILE
        plan = self.graph_compiler.compile(state)

        # EXECUTE DAG
        # LLM-вызовы, repair loop и snapshot — внутри DAGExecutor
        state = await self.dag_executor.execute(
            plan=plan,
            state=state,
            context=self._build_context(),
        )

        return state.final_result

    def _build_context(self) -> dict:
        return {
            "executors": self.executors,
        }