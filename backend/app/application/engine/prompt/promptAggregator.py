from app.application.engine.prompt.promtContextDTO import PromptContextDTO


class PromptAggregator:

    def build(self, state, dsl_keys):

        return PromptContextDTO(
            dsl_keys=dsl_keys,
            message=state.message,
            node_results=state.node_results,
             session={
                "llm_provider": state.session.llm_provider,
                "user_id": state.session.user_id,
                "meta": state.session.meta,
            },
            
            errors=getattr(state, "errors", None),
        )