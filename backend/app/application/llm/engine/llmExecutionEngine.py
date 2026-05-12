from app.application.llm.engine.dag.executionState import ExecutionState
from app.application.llm.engine.graphs.graphRegistryFactory import GraphRegistryFactory


class llmExecutionEngine:

    def __init__(self, dag_executor, router, node_executor_registry, prompt_compiler, prompt_aggregator):
        self.dag_executor = dag_executor
        self.router = router
        self.node_executor_registry = node_executor_registry
        self.prompt_compiler = prompt_compiler
        self.prompt_aggregator = prompt_aggregator

    async def run(self, task_type, message, session):

        graph = GraphRegistryFactory.build(task_type)

        state = ExecutionState(message, session)

        # ======================
        # DAG EXECUTION
        # ======================
        state = await self.dag_executor.execute(
            graph,
            state,
            self.build_runtime_context()
        )

        # ======================
        # PROMPT LAYER
        # ======================
        prompt_context = self.prompt_aggregator.build(state, task_type)

        messages = self.prompt_compiler.compile(prompt_context)

        client = self.router.get(session.llm_provider)

        return await client.chat(messages)
    
    def build_runtime_context(self):
        return {
            "node_executor_registry": self.node_executor_registry,
        }