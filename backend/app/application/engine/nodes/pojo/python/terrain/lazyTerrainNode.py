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
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService

logger = logging.getLogger(__name__)

_generator = TerrainGeneratorService()


class LazyTerrainWorldMissingError(PythonNodeError):
    """world_uid из сессии не найден в DB — данные сессии некорректны."""
    code = "lazy_terrain_world_missing"
    requires_replan = False
    user_message = "Мир не найден. Данные сессии повреждены."


class LazyTerrainGenerationError(PythonNodeError):
    """generate_minimal вернул пустой список несмотря на валидный мир и локацию — баг генератора."""
    code = "lazy_terrain_generation_failed"
    requires_replan = False
    user_message = "Не удалось сгенерировать terrain для локации."


@register_python(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True, kw_only=True)
class LazyTerrainNode(PythonNode):
    """
    Генерирует и сохраняет anchor-ячейку для локации если has_terrain=False.
    Noop (skipped=True) если terrain уже существует.
    """

    id:   str = "lazy_terrain"
    name: str = "Lazy Terrain Generate"

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
    possible_errors: list = field(default_factory=lambda: [LazyTerrainWorldMissingError, LazyTerrainGenerationError])

    async def execute(self, state, context) -> NodeResult:
        check = state.node_results["check_terrain"]

        if check["has_terrain"]:
            logger.debug(
                "lazy_terrain | skipped — terrain already exists for location=%s",
                check["location_uid"],
            )
            return NodeResult(data={"cells": [], "skipped": True})

        world = await context["world_repo"].get_by_id(check["world_uid"])
        if world is None:
            raise LazyTerrainWorldMissingError(
                f"World '{check['world_uid']}' not found for terrain generation"
            )

        location = await context["location_repo"].get_by_id(check["location_uid"])

        cells = _generator.generate_minimal(world, location)
        if not cells:
            raise LazyTerrainGenerationError(
                f"generate_minimal returned empty for location '{check['location_uid']}'"
            )

        await context["map_cell_repo"].insert_bulk_ignore(cells)

        logger.info(
            "lazy_terrain | generated location=%s cells=%d",
            check["location_uid"], len(cells),
        )

        return NodeResult(data={"cells": [asdict(c) for c in cells], "skipped": False})
