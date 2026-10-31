"""Select failed prepared sections and resolve DSL patches; no repair loop."""

from dataclasses import replace

from pydantic import BaseModel

from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.repair.repairMode import RepairMode
from app.application.engine.runtime.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.runtime.prompt.pojo.nodeSection import NodeSection
from app.application.engine.runtime.prompt.pojo.llmRepairPayload import LLMRepairPayload
from app.application.engine.runtime.repair.pojo.nodeFailureContext import NodeFailureContext


class RepairBuilder:
    def __init__(self, dsl_resolver: DSLResolver) -> None:
        self._dsl_resolver = dsl_resolver

    def build(
        self, base: LLMPayload, failures: tuple[NodeFailureContext[BaseModel], ...], *,
        mode: RepairMode = RepairMode.MAXIMUM,
    ) -> LLMRepairPayload:
        sections = {section.node_id: section for section in base.sections}
        patched: list[NodeSection[BaseModel]] = []
        for failure in failures:
            if failure.identity.node_id not in sections:
                raise KeyError(f"repair node '{failure.identity.node_id}' is not in prepared group")
            section = sections[failure.identity.node_id]
            if failure.output_type is not section.output_type:
                raise TypeError("repair Output schema does not match prepared section")
            patched.append(replace(section, dsl=self._dsl_resolver.resolve(list(failure.dsl_keys), context={"language": base.language})))
        return LLMRepairPayload(
            player_message=base.player_message, language=base.language, global_dsl=base.global_dsl,
            sections=tuple(patched), errors=failures, mode=mode,
        )
