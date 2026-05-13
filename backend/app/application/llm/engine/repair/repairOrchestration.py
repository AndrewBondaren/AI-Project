class RepairOrchestrator:

    def __init__(self, router, validator, repair_builder, patch_applier, dsl_projector):
        self.router = router
        self.validator = validator
        self.repair_builder = repair_builder
        self.patch_applier = patch_applier
        self.dsl_projector = dsl_projector

    async def run(self, state, session, system_prompt, dsl_keys, max_attempts: int):
        client = self.router.get(session.llm_provider)
        failed_nodes = self._collect_failed(state)
        failed_nodes = self.dsl_projector.project(failed_nodes, state)
        last_response = None

        for attempt in range(max_attempts):

            repair_input = self.repair_builder.build(
                state=state,
                failed_nodes=failed_nodes,
                dsl_keys=dsl_keys,
                attempt=attempt
            )

            repair_response = await client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": repair_input},
                ],
                model=session.model
            )

            last_response = repair_response

            validation = self.validator.validate(repair_response, state)

            if validation.ok:
                self.patch_applier.apply(state, repair_response)
                return state

            failed_nodes = self._update_failed_nodes(
                failed_nodes,
                validation
            )

        return {
            "status": "failed",
            "reason": "max_attempts_reached",
            "last_response": last_response,
            "failed_nodes": failed_nodes,
        }