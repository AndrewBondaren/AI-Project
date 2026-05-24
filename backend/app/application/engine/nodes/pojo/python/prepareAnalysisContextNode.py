from dataclasses import dataclass, field

from app.application.engine.nodes.pojo.pythonNode import PythonNode


async def prepare_analysis_context(state, context=None):
    return {
        "message": state.message,
        "analysis_depth": "deep",
    }


@dataclass(frozen=True, kw_only=True)
class PrepareAnalysisContextNode(PythonNode):
    id: str = "prepare_context"
    name: str = "Prepare Analysis Context"
    supported_tasks: list = field(default_factory=list)  # или list[TaskType]
    rules: list = field(default_factory=list)            # или list[Rule]
    deps: list[str] = field(default_factory=list)
    handler = prepare_analysis_context  # без field() — callable как class attribute
