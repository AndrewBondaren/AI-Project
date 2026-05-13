from app.application.llm.engine.dag.executionState import ExecutionState
from app.application.llm.engine.graphs.graphRegistryFactory import GraphRegistryFactory


class llmExecutionEngine:

    def __init__(self, dag_executor, router, node_executor_registry, prompt_aggregator, prompt_compiler, dsl_aggregator, validator, dsl_resolver):
        self.dag_executor = dag_executor
        self.router = router
        self.node_executor_registry = node_executor_registry
        self.prompt_aggregator = prompt_aggregator
        self.prompt_compiler = prompt_compiler
        self.dsl_aggregator = dsl_aggregator
        self.validator = validator
        self.dsl_resolver = dsl_resolver

    async def run(self, task_type, message, session):

        graph = GraphRegistryFactory.build(task_type)
        state = ExecutionState(message, session)

        # DAG EXECUTION
        state = await self.dag_executor.execute(
            graph,
            state,
            self.build_runtime_context()
        )
        state.execution_order
        dsl_keys = self.dsl_aggregator.aggregate_dsl_keys(state)

        dsl_context = self.prompt_aggregator.build(state, dsl_keys)
        system_prompt = self.prompt_compiler.compile_system(dsl_context)

        if self.repair_orchestrator.has_failures(state):

            state = await self.repair_orchestrator.run(
                state=state,
                session=session,
                system_prompt=system_prompt,
                dsl_keys=dsl_keys,
                max_attempts=session.repair_iterations  # ← ВОТ ТВОЯ МАСШТАБИРУЕМОСТЬ
            )

        return state.final_result
    
    def build_runtime_context(self):
        return {
            "node_executor_registry": self.node_executor_registry,
        }