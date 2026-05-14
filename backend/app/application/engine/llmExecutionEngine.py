from app.application.engine.dag.executionState import ExecutionState


class LLMExecutionEngine:

    def __init__(
        self,
        dag_executor,
        graph_compiler,
        router,
        prompt_aggregator,
        prompt_compiler,
        dsl_aggregator,
        validator,
        repair_orchestrator,
        executors: dict,
    ):
        self.dag_executor = dag_executor
        self.graph_compiler = graph_compiler
        self.router = router
        self.prompt_aggregator = prompt_aggregator
        self.prompt_compiler = prompt_compiler
        self.dsl_aggregator = dsl_aggregator
        self.validator = validator
        self.repair_orchestrator = repair_orchestrator
        self.executors = executors  # dict: executor_cls → executor instance

    async def run(self, task_type, message, session):

        state = ExecutionState(message, session)
        state.task_type = task_type

        # COMPILE
        plan = self.graph_compiler.compile(state)

        # EXECUTE DAG
        state = await self.dag_executor.execute(
            plan=plan,
            state=state,
            context=self._build_context()
        )

        # AGGREGATE → PROMPT
        dsl_keys = self.dsl_aggregator.aggregate_dsl_keys(state)
        dsl_context = self.prompt_aggregator.build(state, dsl_keys)
        system_prompt = self.prompt_compiler.compile_system(dsl_context)

        # REPAIR если есть failures
        if self.repair_orchestrator.has_failures(state):
            state = await self.repair_orchestrator.run(
                state=state,
                session=session,
                system_prompt=system_prompt,
                dsl_keys=dsl_keys,
                max_attempts=session.repair_iterations
            )

        return state.final_result

    def _build_context(self) -> dict:
        return {
            "executors": self.executors,
            "contract_validator": self.validator,
            "router": self.router,
        }