import logging
from dataclasses import dataclass, field
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType

logger = logging.getLogger(__name__)


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class TerrainContextNode(PythonNode):
    """
    Собирает результат eager или lazy в shared_context["terrain"].
    Downstream LLM-ноды читают terrain из shared_context.
    """

    id:   str = "terrain_context"
    name: str = "Terrain Context"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=lambda: [
        TaskType.SCENE_NARRATION,
        TaskType.SCENE_COMBAT,
        TaskType.SCENE_CHANGE_LOCATION,
        TaskType.LOCAL_SCENE_ANALYSIS,
    ])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=lambda: ["check_terrain", "eager_terrain", "lazy_terrain"])
    possible_errors: list = field(default_factory=list)

    async def execute(self, state, context) -> NodeResult:
        check = state.node_results["check_terrain"]
        eager = state.node_results["eager_terrain"]
        lazy  = state.node_results["lazy_terrain"]

        cells     = eager["cells"] if not eager["skipped"] else lazy["cells"]
        generated = not lazy["skipped"]
        source    = "lazy" if generated else "eager"

        state.shared_context["terrain"] = {
            "location_uid":  check["location_uid"],
            "location_name": check["location_name"],
            "map_x":         check["map_x"],
            "map_y":         check["map_y"],
            "map_z":         check["map_z"],
            "cells":         cells,
            "generated":     generated,
        }

        if not cells:
            logger.warning(
                "terrain_context | 0 cells for location=%s source=%s",
                check["location_uid"], source,
            )
        else:
            logger.info(
                "terrain_context | location=%s cells=%d source=%s map=(%d,%d,%d)",
                check["location_uid"], len(cells), source,
                check["map_x"], check["map_y"], check["map_z"],
            )

        return NodeResult(data={"terrain_loaded": True, "cell_count": len(cells)})
