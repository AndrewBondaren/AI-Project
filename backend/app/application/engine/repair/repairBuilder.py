import json

from app.application.engine.prompt.dslRegistry import DSLRegistry
from app.application.engine.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.application.engine.prompt.pojo.llmRepairPayload import LLMRepairPayload


class RepairBuilder:
    """
    Собирает repair payload для failed LLM-нод.
    Вызывается из RepairOrchestrator на каждой итерации repair loop.
    """

    def __init__(self, payload_builder: LLMGroupPayloadBuilder):
        self.payload_builder = payload_builder


    def build(
        self,
        failed_nodes: list,
        dsl_keys: dict,
        node_errors: dict,
        state,
    ) -> LLMRepairPayload:

        base = self.payload_builder.build(
            nodes=failed_nodes,
            dsl_keys=dsl_keys,
            state=state,
        )

        return LLMRepairPayload(
            player_message=base.player_message,
            language=base.language,
            contract_json=base.contract_json,
            sections=base.sections,
            errors=node_errors,
        )

    def _build_contracts(self, nodes) -> dict:
        return {
            node.id: node.contract_json.model_json_schema()
            for node in nodes
            if node.contract_json is not None
        }

    def _resolve_dsl(self, keys: list[str]) -> str:
        parts = [self.dsl_registry.get(key) for key in keys]
        return "\n\n".join(parts)

    def _collect_deps(self, node, state) -> dict:
        return {
            dep: state.node_results.get(dep)
            for dep in node.deps
            if dep in state.node_results
        }