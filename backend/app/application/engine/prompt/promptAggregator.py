from backend.app.application.engine.prompt.promtContextDTO import PromptContextDTO


class PromptAggregator:

    def build(self, state, dsl_keys):

#        executed_nodes = [
 #           graph.nodes[node_id]
  #          for node_id in state.node_results.keys()
   #     ]
#
 #       dsl_keys = [
  #          node.dsl
   #         for node in executed_nodes
    #        if hasattr(node, "dsl") and node.dsl
     #   ]

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