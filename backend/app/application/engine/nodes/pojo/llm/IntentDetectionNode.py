from app.application.engine.nodes.pojo.llmNodeSpec import LLMNodeSpec
from app.application.contracts.contracts import NarrationContract


class ResponseGenerationNode(LLMNodeSpec):

    id = "response_generation"
    graph = "chat"
    name = "Response Generation"

    dsl = "chat_response"
    contract = NarrationContract

    deps = ("intent_detection",)