from app.application.engine.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.prompt.pojo.nodeSection import NodeSection


class LLMGroupPayloadBuilder:
    """
    Собирает агрегированный JSON-запрос для одной temperature-группы.

    Не трогает DSLRegistry, PromptCompiler и остальную prompt-цепочку —
    те работают для глобального промпта в LLMExecutionEngine.
    """

    def build(self, nodes: list, state) -> dict:

        return LLMPayload(
            player_message=state.message,
            language=state.session.language,
            contract_json=self._build_contracts(nodes),
            sections={
                node.id: NodeSection(
                    dsl=self._resolve_dsl(dsl_keys[node.id]),
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
    
    #Уточнить насколько место этому методу тут.
    def _resolve_dsl(self, keys: list[str]) -> str:
        parts = [self.dsl_registry.get(key) for key in keys]
        return "\n\n".join(parts)

    def _collect_deps(self, node, state) -> dict:
        return {
            dep: state.node_results[dep]
            for dep in node.deps
            if dep in state.node_results
        }