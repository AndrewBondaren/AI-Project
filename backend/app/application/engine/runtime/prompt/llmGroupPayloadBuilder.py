"""Compose one LLM group from prepared, bound Inputs; no runtime reads."""

from typing import cast

from pydantic import BaseModel

from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.nodeTypes.support.nodeKind import NodeKind
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.runtime.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.runtime.prompt.pojo.nodeSection import NodeSection
from app.dataModel.engine.dag.errors.nodeError import NodeError

_GLOBAL_DSL_KEY = "llm_group"


def _validate_keys(value: object) -> None:
    if not isinstance(value, tuple) or any(not isinstance(key, str) for key in cast(tuple[object, ...], value)):
        raise TypeError("DSL keys must be a tuple of strings")


class LLMGroupPayloadBuilder:
    def __init__(self, dsl_resolver: DSLResolver) -> None:
        self._dsl_resolver = dsl_resolver

    def section[I: BaseModel, O: BaseModel, E: NodeError](
        self, node: LLMNode[I, O, E], registration: NodeRegistration[I, O, E], input: I, *,
        language: str, dsl_keys: tuple[str, ...] | None = None,
    ) -> NodeSection[I]:
        registration.validate_node(node)
        if registration.kind != NodeKind.LLM:
            raise TypeError("LLM payload requires an LLM binding")
        keys = (node.dsl,) if dsl_keys is None else dsl_keys
        _validate_keys(keys)
        return NodeSection(
            node_id=registration.node_id, input_type=registration.contract.input_type, input=input,
            output_type=registration.contract.output_type,
            dsl=self._dsl_resolver.resolve(list(keys), context={"language": language}),
        )

    def build(
        self, sections: tuple[NodeSection[BaseModel], ...], *, player_message: str, language: str,
    ) -> LLMPayload:
        return LLMPayload(
            player_message=player_message, language=language, sections=sections,
            global_dsl=self._dsl_resolver.resolve([_GLOBAL_DSL_KEY]),
        )
