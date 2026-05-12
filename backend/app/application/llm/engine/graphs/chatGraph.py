from app.application.llm.engine.nodes.nodeFactory import NodeFactory


def build_chat_graph():

    return {
        "intent_detection": NodeFactory.llm(
            id="intent_detection",
            name="Intent Detection",
            dsl="intent_router",
        ),

        "response_generation": NodeFactory.llm(
            id="response_generation",
            name="Response Generation",
            dsl="chat_response",
            deps=["intent_detection"]
        )
    }