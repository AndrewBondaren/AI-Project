from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.prompt.pojo.nodeSection import NodeSection


class LLMGroupPayloadBuilder:

    def __init__(self, dsl_resolver: DSLResolver):
        self.dsl_resolver = dsl_resolver

    def build(self, nodes: list, dsl_keys: dict, state) -> LLMPayload:
        return LLMPayload(
            player_message=state.message,
            language=state.session.language,
            contract_json=self._build_contracts(nodes),
            sections={
                node.id: NodeSection(
                    dsl=self.dsl_resolver.resolve(dsl_keys[node.id]),
                    context_data=self._collect_deps(node, state),
                )
                for node in nodes
            },
        )

    def _build_contracts(self, nodes: list) -> dict:
        return {
            node.id: node.contract_json.model_json_schema()
            for node in nodes
            if node.contract_json is not None
        }

    def _collect_deps(self, node, state) -> dict:
        return {
            dep: state.node_results[dep]
            for dep in node.deps
            if dep in state.node_results
        }