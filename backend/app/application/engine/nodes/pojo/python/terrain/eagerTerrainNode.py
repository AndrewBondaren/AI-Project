import logging
from dataclasses import asdict, dataclass, field
from typing_extensions import Literal

from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register_python
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNode import PythonNode
from app.application.engine.nodes.pojo.pythonNodeError import PythonNodeError
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType

logger = logging.getLogger(__name__)


class EagerTerrainEmptyError(PythonNodeError):
    """has_terrain=True, но get_by_location вернул пустой список — несогласованность DB."""
    code = "eager_terrain_empty"
    requires_replan = False
    user_message = "Данные terrain повреждены. Обратитесь к администратору."


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class EagerTerrainNode(PythonNode):
    """
    Загружает готовые MapCells из DB если has_terrain=True.
    Noop (skipped=True) если terrain ещё не сгенерирован.
    """

    id:   str = "eager_terrain"
    name: str = "Eager Terrain Load"

    phase:          Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True

    supported_tasks: list = field(default_factory=lambda: [
        TaskType.SCENE_NARRATION,
        TaskType.SCENE_COMBAT,
        TaskType.SCENE_CHANGE_LOCATION,
        TaskType.LOCAL_SCENE_ANALYSIS,
    ])
    rules:           list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps:            list = field(default_factory=lambda: ["check_terrain"])
    possible_errors: list = field(default_factory=lambda: [EagerTerrainEmptyError])

    async def execute(self, state, context) -> NodeResult:
        check = state.node_results["check_terrain"]

        if not check["has_terrain"]:
            logger.debug(
                "eager_terrain | skipped — no terrain in DB for location=%s",
                check["location_uid"],
            )
            return NodeResult(data={"cells": [], "skipped": True})

        cells = await context["map_cell_repo"].get_by_location(check["location_uid"])
        if not cells:
            raise EagerTerrainEmptyError(
                f"has_cells_for_location=True but get_by_location returned empty "
                f"for '{check['location_uid']}'"
            )

        logger.info(
            "eager_terrain | loaded location=%s cells=%d",
            check["location_uid"], len(cells),
        )

        return NodeResult(data={"cells": [asdict(c) for c in cells], "skipped": False})
