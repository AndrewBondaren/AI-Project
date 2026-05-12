from app.application.llm.engine.prompt.promptContext import PromptContext

class PromptAggregator:

    def build(self, state, task_type):

        return PromptContext(
            message=state.message,
            node_results=state.node_results,
            session=getattr(state, "session", None),
            errors=getattr(state, "errors", None),
            task_type=task_type,
        )