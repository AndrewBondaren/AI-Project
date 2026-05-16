class LLMGroupPayloadBuilder:
    """
    Собирает агрегированный JSON-запрос для одной temperature-группы.

    Не трогает DSLRegistry, PromptCompiler и остальную prompt-цепочку —
    те работают для глобального промпта в LLMExecutionEngine.
    """

    def build(self, nodes: list, state) -> dict:

        payload = {
            "player_message": state.message,
            "language": "RU",
            "contract_json": self._build_contracts(nodes),
        }

        for node in nodes:
            payload[node.id] = {
                "dsl": node.dsl,
                "context_data": self._collect_deps(node, state),
            }

        return payload

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