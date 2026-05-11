from typing import Dict
from app.application.llm.response.taskType import TaskType
from app.application.llm.engine.dag.executionGraph import ExecutionGraph
from app.application.llm.engine.dag.executionState import ExecutionState


class llmExecutionEngine:

    def __init__(self, executor, graph_registry: Dict[TaskType, ExecutionGraph]):
        self.executor = executor
        self.graph_registry = graph_registry

    async def run(self, task_type: TaskType, message: str, session):

        graph = self.graph_registry[task_type]
        state = ExecutionState(message, session)

        context = self.build_runtime_context(session)

        return await self.executor.execute(
            graph,
            state,
            context
        )
    
    def build_runtime_context(self, session):

        return {
            "client": self.router.get(session.llm_provider),
            "structured_executor": self.structured_executor,
            "prompt_builder": self.prompt_builder_registry,
        }
    def inject_runtime(self, graph, runtime):

        for node in graph.nodes.values():

            if node.type == "llm":

                node.meta["client"] = runtime["client"]
                node.meta["structured_executor"] = runtime["structured_executor"]
                node.meta["prompt_builder"] = runtime["prompt_builder"]