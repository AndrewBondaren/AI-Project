from backend.app.application.engine.nodes.pojo.PythonNodeSpec import PythonNode


async def prepare_analysis_context(state):

    return {
        "message": state.message,
        "analysis_depth": "deep",
    }


class PrepareAnalysisContextNode(PythonNode):

    def __init__(self):
        super().__init__(
            id="prepare_context",
            name="Prepare Analysis Context",
            deps=[],
            handler=prepare_analysis_context,
        )