from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.prompt.pojo.nodeSection import NodeSection
from app.application.engine.prompt.schemaBuilder import build_strict_schema

_GLOBAL_DSL_KEY = "llm_group"


class LLMGroupPayloadBuilder:

    def __init__(self, dsl_resolver: DSLResolver):
        self.dsl_resolver = dsl_resolver

    def build(self, nodes: list, dsl_keys: dict, state) -> LLMPayload:
        return LLMPayload(
            player_message=state.message,
            language=state.session.language,
            global_dsl=self.dsl_resolver.resolve([_GLOBAL_DSL_KEY]),
            response_format_schema=build_strict_schema({
                node.id: node.contract_json.model_json_schema()
                for node in nodes
                if node.contract_json is not None
            }),
            sections={
                node.id: NodeSection(
                    dsl=self.dsl_resolver.resolve(dsl_keys[node.id]),
                    context_data=self._collect_deps(node, state),
                )
                for node in nodes
            },
        )

    def _collect_deps(self, node, state) -> dict:
        return {
            dep: state.node_results[dep]
            for dep in node.deps
            if dep in state.node_results
        }
