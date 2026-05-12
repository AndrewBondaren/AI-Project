from app.application.llm.engine.nodes.nodeFactory import NodeFactory


# =========================================================
# PYTHON NODES
# =========================================================

async def prepare_analysis_context(state):

    return {
        "message": state.message,
        "analysis_depth": "deep"
    }


async def merge_analysis(state):

    reasoning = state.node_results["reasoning"]
    conclusion = state.node_results["conclusion"]

    return {
        "reasoning": reasoning,
        "conclusion": conclusion
    }


# =========================================================
# GRAPH BUILDER
# =========================================================

def build_analysis_graph():

    return {

        # -----------------------------------------
        # CONTEXT PREPARATION (PYTHON)
        # -----------------------------------------

        "prepare_context": NodeFactory.python(
            id="prepare_context",
            name="Prepare Analysis Context",
            handler=prepare_analysis_context
        ),

        # -----------------------------------------
        # REASONING (LLM)
        # -----------------------------------------

        "reasoning": NodeFactory.llm(
            id="reasoning",
            name="Analysis Reasoning",
            deps=["prepare_context"],
            dsl="analysis_reasoning"
        ),

        # -----------------------------------------
        # CONCLUSION (LLM)
        # -----------------------------------------

        "conclusion": NodeFactory.llm(
            id="conclusion",
            name="Analysis Conclusion",
            deps=["reasoning"],
            dsl="analysis_conclusion"
        ),

        # -----------------------------------------
        # MERGE OUTPUT (PYTHON)
        # -----------------------------------------

        "merge_output": NodeFactory.python(
            id="merge_output",
            name="Merge Analysis Output",
            deps=["conclusion"],
            handler=merge_analysis
        )
    }