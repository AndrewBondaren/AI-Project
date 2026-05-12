from app.application.llm.engine.nodes.llmNode import LLMNode
from app.application.llm.engine.nodes.pythonNode import PythonNode


class NodeFactory:

    @staticmethod
    def llm(
        *,
        id: str,
        name: str,
        dsl: str,
        contract=None,
        deps=None,
        provider=None,
        model=None,
        temperature=0.0,
        max_tokens=1024,
        timeout=None,
        retry_policy=None,
        tags=None,
    ):

        return LLMNode(
            id=id,
            name=name,

            deps=deps or [],

            timeout=timeout,

            retry_policy=retry_policy,

            tags=tags or [],

            dsl=dsl,

            contract=contract,

            provider=provider,

            model=model,

            temperature=temperature,

            max_tokens=max_tokens,
        )

    @staticmethod
    def python(
        *,
        id: str,
        name: str,
        handler,
        deps=None,
        timeout=None,
        retry_policy=None,
        tags=None,
    ):

        return PythonNode(
            id=id,
            name=name,

            deps=deps or [],

            timeout=timeout,

            retry_policy=retry_policy,

            tags=tags or [],

            handler=handler,
        )