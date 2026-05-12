from app.application.llm.engine.taskType import TaskType
from app.application.llm.engine.graphs.executionGraph import ExecutionGraph
from app.application.llm.engine.graphs.chatGraph import build_chat_graph
from app.application.llm.engine.graphs.analysisGraph import build_analysis_graph


class GraphRegistryFactory:

    _builders = {
        TaskType.CHAT: build_chat_graph,
        TaskType.ANALYSIS: build_analysis_graph,
    }

    @classmethod
    def build(cls, task_type: TaskType) -> ExecutionGraph:

        if task_type not in cls._builders:
            raise ValueError(f"No graph builder for task type: {task_type}")

        builder = cls._builders[task_type]

        nodes = builder()  # ← DSL layer (dict[str, Node])

        return ExecutionGraph(nodes)