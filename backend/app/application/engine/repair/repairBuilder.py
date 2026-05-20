from app.application.engine.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.application.engine.prompt.pojo.llmRepairPayload import LLMRepairPayload
from app.application.engine.repair.dslFailureProjector import DSLFailureProjector


class RepairBuilder:

    def __init__(self, payload_builder: LLMGroupPayloadBuilder, failure_projector: DSLFailureProjector):
        self.payload_builder = payload_builder
        self.failure_projector = failure_projector

    def build(
        self,
        failed_nodes: list,
        dsl_keys: dict,
        state,
    ) -> LLMRepairPayload:

        base = self.payload_builder.build(
            nodes=failed_nodes,
            dsl_keys=dsl_keys,
            state=state,
        )

        errors = self.failure_projector.project(failed_nodes, state)

        return LLMRepairPayload(
            player_message=base.player_message,
            language=base.language,
            global_dsl=base.global_dsl,
            response_format_schema=base.response_format_schema,
            sections=base.sections,
            errors=errors,
            mode=state.session.repair_mode,
        )